"""
测试 py/get_seat.py — 座位预约主逻辑
"""
import threading
import time
from unittest.mock import patch, MagicMock

import pytest

from get_seat import (
    ConfirmPacer,
    _first_window_burst,
    random_get_seat,
    check_reservation_status,
    check_book_seat,
    post_to_get_seat,
    select_seat,
    run_seat_reservation,
)
from api.exceptions import ReservationFailed
from classrooms import EXCLUDE_ID
from config.config import AppConfig
from api.http import RequestFailed


# ========== random_get_seat ==========

class TestRandomGetSeat:
    """随机选座"""

    def test_returns_id(self):
        """从列表随机返回一个 id"""
        data = [{"id": "100"}, {"id": "200"}, {"id": "300"}]
        result = random_get_seat(data)
        assert result in ["100", "200", "300"]

    def test_single_item(self):
        """单个座位返回该 id"""
        data = [{"id": "42"}]
        assert random_get_seat(data) == "42"

    def test_empty_raises(self):
        """空列表抛出 IndexError"""
        with pytest.raises(IndexError):
            random_get_seat([])


# ========== check_reservation_status ==========

class TestCheckReservationStatus:
    """预约状态检测"""

    def test_success(self, sample_config, fake_token_mgr):
        """预约成功"""
        with patch("get_seat.check_book_seat") as mock_check:
            mock_check.return_value = True
            result = check_reservation_status(
                {"msg": "预约成功"}, sample_config, fake_token_mgr, []
            )
        assert result is True

    def test_duplicate(self, sample_config, fake_token_mgr):
        """重复预约"""
        with patch("get_seat.check_book_seat") as mock_check:
            mock_check.return_value = True
            result = check_reservation_status(
                {"msg": "当前用户在该时段已存在座位预约，不可重复预约"},
                sample_config, fake_token_mgr, [],
            )
        assert result is True

    def test_not_open(self, sample_config, fake_token_mgr):
        """未到预约时间"""
        result = check_reservation_status(
            {"msg": "开放预约时间19:20"}, sample_config, fake_token_mgr, []
        )
        assert result is False

    def test_not_logged_in(self, sample_config, fake_token_mgr):
        """未登录触发 token 刷新"""
        result = check_reservation_status(
            {"msg": "您尚未登录"}, sample_config, fake_token_mgr, []
        )
        fake_token_mgr.get_token.assert_called()
        assert result is False

    def test_cancel_success_exits(self, sample_config, fake_token_mgr):
        """取消成功返回 True（不再退出）"""
        result = check_reservation_status(
            {"msg": "取消成功"}, sample_config, fake_token_mgr, []
        )
        assert result is True

    def test_unknown_msg(self, sample_config, fake_token_mgr):
        """未知消息不视为成功，继续重试"""
        result = check_reservation_status(
            {"msg": "未知状态"}, sample_config, fake_token_mgr, []
        )
        assert result is False

    def test_invalid_input_retries(self, sample_config, fake_token_mgr):
        """非 dict 输入（服务端削峰）不退出，交给额度闸门重试"""
        result = check_reservation_status(
            "not a dict", sample_config, fake_token_mgr, []
        )
        assert result is False


# ========== check_book_seat ==========

class TestCheckBookSeat:
    """检查已预约座位"""

    @patch("get_seat.get_member_seat")
    def test_found_reservation(self, mock_member, sample_config, fake_token_mgr):
        """已预约成功"""
        mock_member.return_value = {
            "data": {
                "data": [{"statusName": "预约成功", "name": "001", "nameMerge": "综合楼-801 001"}]
            }
        }
        messages = []
        result = check_book_seat(sample_config, fake_token_mgr, messages, "bearer token")
        assert result is True

    @patch("get_seat.get_member_seat")
    def test_no_reservation(self, mock_member, sample_config, fake_token_mgr):
        """无预约"""
        mock_member.return_value = {
            "data": {
                "data": [{"statusName": "已取消", "name": "001", "nameMerge": "test"}]
            }
        }
        result = check_book_seat(sample_config, fake_token_mgr, [], "bearer token")
        assert result is False

    @patch("get_seat.get_member_seat")
    def test_not_logged_in_refreshes(self, mock_member, sample_config, fake_token_mgr):
        """未登录时刷新 token"""
        mock_member.return_value = {"msg": "您尚未登录"}
        check_book_seat(sample_config, fake_token_mgr, [], "bearer token")
        fake_token_mgr.get_token.assert_called()

    @patch("get_seat.get_member_seat")
    def test_member_none(self, mock_member, sample_config, fake_token_mgr):
        """返回 None 不崩溃"""
        mock_member.return_value = None
        result = check_book_seat(sample_config, fake_token_mgr, [], "bearer token")
        assert result is False


# ========== select_seat ==========

class TestSelectSeat:
    """选座主逻辑"""

    @pytest.fixture(autouse=True)
    def _no_release_wait(self, monkeypatch):
        """这些用例覆盖的是放座后的循环，不要真的睡到当天 19:20。"""
        monkeypatch.setattr("get_seat.release_epoch", lambda _cfg: None)
        monkeypatch.setattr("get_seat.STEADY_GAP", 0.0)

    @patch("get_seat.post_to_get_seat")
    @patch("get_seat.get_seat_info")
    def test_mode3_random(self, mock_seat_info, mock_post, sample_config, fake_token_mgr):
        """模式 3：随机选择后 sys.exit（retries 满）"""
        sample_config.mode = "3"
        mock_seat_info.return_value = [
            {"id": "100", "no": "001"},
            {"id": "101", "no": "002"},
        ]
        mock_post.return_value = None
        # select_seat 循环 100 次后抛 ReservationFailed
        with patch("get_seat.send_message"):
            with pytest.raises(ReservationFailed):
                select_seat(16, 999, "2026-06-28", sample_config, fake_token_mgr, [])
        # post_to_get_seat 被调用了
        assert mock_post.call_count >= 1

    @patch("get_seat.post_to_get_seat")
    @patch("get_seat.get_seat_info")
    def test_mode2_excludes(self, mock_seat_info, mock_post, sample_config, fake_token_mgr):
        """模式 2：排除 EXCLUDE_ID 中的座位"""
        sample_config.mode = "2"
        # 第一个座位在 EXCLUDE_ID 中，第二个不在
        excluded_id = list(EXCLUDE_ID)[0]
        mock_seat_info.return_value = [
            {"id": excluded_id, "no": "001"},
            {"id": "99999", "no": "002"},
        ]
        mock_post.return_value = None
        # 循环结束后 sys.exit
        with patch("get_seat.send_message"):
            with pytest.raises(ReservationFailed):
                select_seat(16, 999, "2026-06-28", sample_config, fake_token_mgr, [])
        # 每次调用 post_to_get_seat 时选中的都是 99999（非排除的）
        for call in mock_post.call_args_list:
            assert call[0][0] == "99999"

    @patch("get_seat.post_to_get_seat")
    @patch("get_seat.get_seat_info")
    def test_mode1_filters_range(self, mock_seat_info, mock_post, sample_config, fake_token_mgr):
        """模式 1：范围过滤"""
        sample_config.mode = "1"
        sample_config.seat_id = [[100, 102]]
        mock_seat_info.return_value = [
            {"id": "100", "no": "001"},
            {"id": "101", "no": "002"},
            {"id": "200", "no": "100"},  # 超出范围
        ]
        mock_post.return_value = None
        with patch("get_seat.send_message"):
            with pytest.raises(ReservationFailed):
                select_seat(16, 999, "2026-06-28", sample_config, fake_token_mgr, [])
        # 每次选中的座位 ID 都在 100-102 范围内
        for call in mock_post.call_args_list:
            assert call[0][0] in ["100", "101"]

    @patch("get_seat.get_seat_info")
    def test_mode4_wrong_build_skips(self, mock_seat_info, sample_config, fake_token_mgr):
        """模式 4 + build_id != 22 → 循环 100 次后退出"""
        sample_config.mode = "4"
        mock_seat_info.return_value = [{"id": "100", "no": "228"}]
        with patch("get_seat.send_message"):
            with pytest.raises(ReservationFailed):
                select_seat(16, 999, "2026-06-28", sample_config, fake_token_mgr, [])

    @patch("get_seat.post_to_get_seat")
    @patch("get_seat.get_seat_info")
    def test_mode4_target_found(self, mock_seat_info, mock_post, sample_config, fake_token_mgr):
        """模式 4 + 座位 228 可用，选中后继续循环"""
        sample_config.mode = "4"
        mock_seat_info.return_value = [
            {"id": "5001", "no": "228"},
            {"id": "5002", "no": "229"},
        ]
        mock_post.return_value = None
        with patch("get_seat.send_message"):
            with pytest.raises(ReservationFailed):
                select_seat(22, 999, "2026-06-28", sample_config, fake_token_mgr, [])
        # 每次都选中 228 号座位
        for call in mock_post.call_args_list:
            assert call[0][0] == "5001"

    @patch("get_seat.get_seat_info")
    def test_unknown_mode_breaks(self, mock_seat_info, sample_config, fake_token_mgr):
        """非法模式 → break"""
        sample_config.mode = "99"
        mock_seat_info.return_value = [{"id": "100", "no": "001"}]
        select_seat(16, 999, "2026-06-28", sample_config, fake_token_mgr, [])
        # 只调用一次就 break
        assert mock_seat_info.call_count == 1

    @patch("get_seat.get_seat_info")
    def test_empty_data_breaks(self, mock_seat_info, sample_config, fake_token_mgr):
        """空座位列表 → break"""
        sample_config.mode = "3"
        mock_seat_info.return_value = []
        messages = []
        select_seat(16, 999, "2026-06-28", sample_config, fake_token_mgr, messages)
        assert mock_seat_info.call_count == 1
        assert any("获取座位信息失败" in m for m in messages)


# ========== run_seat_reservation ==========

class TestRunSeatReservation:
    """预约主流程"""

    @patch("get_seat.send_message")
    @patch("get_seat.select_seat")
    @patch("get_seat.get_segment")
    @patch("get_seat.get_build_id")
    @patch("get_seat.get_date")
    def test_full_flow(
        self, mock_date, mock_build, mock_seg, mock_select, mock_send,
        sample_config, fake_token_mgr
    ):
        """遍历所有教室"""
        mock_date.return_value = "2026-06-28"
        mock_build.return_value = 16
        mock_seg.return_value = 999
        sample_config.classrooms_name = ["综合楼-801自习室", "综合楼-803自习室"]

        run_seat_reservation(sample_config, fake_token_mgr)
        assert mock_select.call_count == 2


# ========== 放座瞬间并发三连发 ==========

class TestConfirmPacer:
    """额度闸门：并发调用下也必须守住「每窗口最多 CAP 发」"""

    def test_concurrent_wait_never_exceeds_cap(self, monkeypatch):
        monkeypatch.setattr("get_seat.CONFIRM_WINDOW", 0.3)
        monkeypatch.setattr("get_seat.CONFIRM_CAP", 3)
        pacer = ConfirmPacer()
        stamps = []
        lock = threading.Lock()

        def worker():
            pacer.wait()
            with lock:
                stamps.append(time.time())

        threads = [threading.Thread(target=worker) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stamps.sort()
        # 任意 4 发都不能落在同一个窗口内
        for i in range(len(stamps) - 3):
            assert stamps[i + 3] - stamps[i] >= 0.28


class TestFirstWindowBurst:
    """三连发：发送与响应解耦"""

    def test_success_from_any_send(self, sample_config, fake_token_mgr):
        calls = []

        def fake_confirm(*args, **kwargs):
            calls.append(time.time())
            return {"msg": "预约成功"}

        with patch("get_seat._raw_confirm", side_effect=fake_confirm), \
                patch("get_seat.check_reservation_status", return_value=True):
            got, sent = _first_window_burst(
                "198", "9150", 999, sample_config, fake_token_mgr, [], {"open": False})

        assert got is True
        assert sent == 3
        assert len(calls) == 3

    def test_slow_response_does_not_block_sends(self, sample_config, fake_token_mgr,
                                                monkeypatch):
        monkeypatch.setattr("get_seat.BURST_GAP", 0.2)
        monkeypatch.setattr("get_seat.BURST_DRAIN", 0.3)
        started = []
        release = threading.Event()

        def slow_confirm(*args, **kwargs):
            started.append(time.time())
            release.wait(5)
            return {"msg": "开放预约时间19:20"}

        try:
            with patch("get_seat._raw_confirm", side_effect=slow_confirm), \
                    patch("get_seat.check_reservation_status", return_value=False):
                t0 = time.time()
                got, sent = _first_window_burst(
                    "198", "9150", 999, sample_config, fake_token_mgr, [], {"open": False})
                elapsed = time.time() - t0
        finally:
            release.set()

        assert got is False
        assert sent == 3
        assert len(started) == 3      # 第一发未返回时，后两发也已经发出
        assert elapsed < 1.5          # 0.4s 发完 + 0.3s 等结果


class TestSelectSeatBurst:
    """select_seat 在放座瞬间走三连发，而不是单发串行"""

    @patch("get_seat._first_window_burst")
    @patch("get_seat._warm_up_before_release")
    @patch("get_seat._mode5_targets")
    @patch("get_seat.release_epoch")
    def test_mode5_burst_at_release(self, mock_release, mock_targets, mock_warm,
                                    mock_burst, sample_config, fake_token_mgr):
        sample_config.mode = "5"
        sample_config.seat_id = [198]
        mock_release.return_value = time.time() + 0.05
        mock_targets.return_value = [("198", "9150")]
        mock_warm.return_value = False
        mock_burst.return_value = (True, 3)

        result = select_seat(49, 999, "2026-10-25", sample_config, fake_token_mgr, [])

        assert result is True
        mock_burst.assert_called_once()
