/**
 * 管理面板前端逻辑
 *
 * 所有 fetch 请求均设置 X-Requested-With: XMLHttpRequest 头（与后端 _csrf_guard 配合）
 */
(function () {
    "use strict";

    const API = {
        auth: "/admin/api/auth",
        logout: "/admin/api/logout",
        users: "/admin/api/users",
        order: "/admin/api/users/order",
        grab: "/admin/api/grab",
        grabStatus: "/admin/api/grab/status",
        logs: "/admin/api/logs",
    };

    // 抢座顺序的本地工作副本（保存时一次性提交）
    let grabOrder = [];
    let grabStatusTimer = null;

    // ---------- 通用工具 ----------

    function showToast(message, type) {
        const toast = document.getElementById("toast");
        toast.textContent = message;
        toast.className = "toast show " + (type || "success");
        setTimeout(() => {
            toast.className = "toast " + (type || "success");
        }, 2500);
    }

    async function fetchJSON(url, options) {
        const opts = options || {};
        opts.headers = Object.assign({ "X-Requested-With": "XMLHttpRequest" }, opts.headers || {});
        if (opts.body && typeof opts.body === "object") {
            opts.headers["Content-Type"] = "application/json";
            opts.body = JSON.stringify(opts.body);
        }
        const resp = await fetch(url, opts);
        let data;
        try {
            data = await resp.json();
        } catch (e) {
            data = { success: false, error: "响应解析失败" };
        }
        if (!resp.ok && data.success === undefined) {
            data.success = false;
        }
        return data;
    }

    function escapeHTML(s) {
        if (s === null || s === undefined) return "";
        return String(s).replace(/[&<>"']/g, (c) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        })[c]);
    }

    function maskPassword(p) {
        if (!p) return "";
        if (p.length <= 2) return "*".repeat(p.length);
        return p[0] + "*".repeat(p.length - 2) + p[p.length - 1];
    }

    /**
     * 切换密码输入框可见性
     * 通过 data-target 指向 input id
     */
    function togglePasswordVisibility(btn) {
        const targetId = btn.getAttribute("data-target");
        if (!targetId) return;
        const input = document.getElementById(targetId);
        if (!input) return;
        const isHidden = input.type === "password";
        input.type = isHidden ? "text" : "password";
        const eyeIcon = btn.querySelector(".icon-eye");
        const eyeOffIcon = btn.querySelector(".icon-eye-off");
        if (eyeIcon) eyeIcon.style.display = isHidden ? "none" : "";
        if (eyeOffIcon) eyeOffIcon.style.display = isHidden ? "" : "none";
    }

    // ---------- 登录/退出 ----------

    async function login() {
        const password = document.getElementById("loginPassword").value;
        if (!password) {
            showToast("请输入密码", "error");
            return;
        }
        const data = await fetchJSON(API.auth, { method: "POST", body: { password } });
        if (data.success) {
            showToast("登录成功", "success");
            showMainView();
        } else {
            showToast(data.error || "登录失败", "error");
        }
    }

    async function logout() {
        await fetchJSON(API.logout, { method: "POST" });
        showLoginView();
        showToast("已退出", "success");
    }

    function showLoginView() {
        document.getElementById("loginView").classList.remove("hidden");
        document.getElementById("mainView").classList.add("hidden");
        document.getElementById("loginPassword").value = "";
    }

    async function showMainView() {
        document.getElementById("loginView").classList.add("hidden");
        document.getElementById("mainView").classList.remove("hidden");
        await Promise.all([loadUsers(), refreshGrabStatus(), loadLogs()]);
    }

    // ---------- 账号列表 ----------

    async function loadUsers() {
        const data = await fetchJSON(API.users);
        if (!data.success) {
            showToast(data.error || "加载账号失败", "error");
            return;
        }
        renderUsersTable(data.users);
        grabOrder = data.grab_order || [];
        renderOrderList();
    }

    function renderUsersTable(users) {
        const tbody = document.getElementById("usersTable");
        if (!users || users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:#909399;">暂无账号，点击右上角"新增账号"</td></tr>';
            return;
        }
        tbody.innerHTML = users.map((u) => {
            const seatDisplay = formatSeatForTable(u.seat_id, u.mode);
            return `<tr>
                <td>${escapeHTML(u.username)}</td>
                <td>${escapeHTML(maskPassword(u.password))}</td>
                <td>模式 ${escapeHTML(u.mode)}</td>
                <td style="max-width:200px; word-break:break-all;">${escapeHTML(seatDisplay)}</td>
                <td style="max-width:200px; word-break:break-all;">${escapeHTML((u.classrooms_name || []).join("; "))}</td>
                <td>${escapeHTML(u.date === "tomorrow" ? "明天" : "今天")}</td>
                <td>${escapeHTML(u.push_method || "无")}</td>
                <td>
                    <button class="btn-primary btn-sm" onclick="openEditUserModal('${escapeHTML(u.username)}')">编辑</button>
                    <button class="btn-danger btn-sm" onclick="deleteUser('${escapeHTML(u.username)}')">删除</button>
                </td>
            </tr>`;
        }).join("");
        // 缓存用户列表，供编辑使用
        window._usersCache = users;
    }

    function formatSeatForTable(seatId, mode) {
        if (!seatId || seatId.length === 0) return "—";
        if (mode === "1") {
            // 范围对：[[7480,7519],[7544,7567]]
            return seatId.map((s) => Array.isArray(s) ? `[${s[0]},${s[1]}]` : String(s)).join("; ");
        }
        // 模式 4：优先座位号数组
        return seatId.map((s) => Array.isArray(s) ? s.join(",") : String(s)).join("; ");
    }

    // ---------- 抢座顺序 ----------

    function renderOrderList() {
        const container = document.getElementById("orderList");
        if (grabOrder.length === 0) {
            container.innerHTML = '<p class="hint">暂无抢座顺序配置</p>';
            return;
        }
        container.innerHTML = grabOrder.map((u, i) => `
            <div class="order-item">
                <span class="index">#${i + 1}</span>
                <span class="username">${escapeHTML(u)}</span>
                <span class="order-actions">
                    <button class="btn-sm btn-primary" onclick="moveOrder(${i}, -1)" ${i === 0 ? "disabled" : ""}>↑</button>
                    <button class="btn-sm btn-primary" onclick="moveOrder(${i}, 1)" ${i === grabOrder.length - 1 ? "disabled" : ""}>↓</button>
                </span>
            </div>
        `).join("");
    }

    function moveOrder(index, delta) {
        const newIndex = index + delta;
        if (newIndex < 0 || newIndex >= grabOrder.length) return;
        const tmp = grabOrder[index];
        grabOrder[index] = grabOrder[newIndex];
        grabOrder[newIndex] = tmp;
        renderOrderList();
    }

    async function saveOrder() {
        const data = await fetchJSON(API.order, { method: "PUT", body: { grab_order: grabOrder } });
        if (data.success) {
            showToast("顺序已保存", "success");
        } else {
            showToast(data.error || "保存失败", "error");
        }
    }

    // ---------- 抢座任务 ----------

    async function triggerGrab() {
        if (!confirm("确认立即触发顺序抢座？将按抢座顺序依次执行。")) return;
        const data = await fetchJSON(API.grab, { method: "POST" });
        if (data.success) {
            showToast("抢座任务已启动", "success");
            startGrabStatusPolling();
        } else {
            showToast(data.error || "启动失败", "error");
        }
    }

    async function refreshGrabStatus() {
        const data = await fetchJSON(API.grabStatus);
        if (!data.success) return;
        renderGrabStatus(data.state);
    }

    function renderGrabStatus(state) {
        const badge = document.getElementById("grabStatus");
        const resultsDiv = document.getElementById("grabResults");

        if (state.running) {
            badge.className = "status-badge status-running";
            badge.textContent = "运行中";
        } else if (state.results && state.results.length > 0) {
            const allSuccess = state.results.every((r) => r.success);
            badge.className = "status-badge " + (allSuccess ? "status-success" : "status-failed");
            badge.textContent = allSuccess ? "全部成功" : "部分失败";
        } else {
            badge.className = "status-badge status-idle";
            badge.textContent = "空闲";
        }

        if (state.results && state.results.length > 0) {
            resultsDiv.innerHTML = "<strong>执行结果：</strong><ul style=\"margin-top:8px; padding-left:20px;\">" +
                state.results.map((r) => `<li>${escapeHTML(r.username)}: ${r.success ? "✅ 成功" : "❌ 失败 (" + escapeHTML(r.error || "") + ")"}</li>`).join("") +
                "</ul>";
        } else {
            resultsDiv.innerHTML = "";
        }
    }

    function startGrabStatusPolling() {
        if (grabStatusTimer) clearInterval(grabStatusTimer);
        grabStatusTimer = setInterval(async () => {
            await refreshGrabStatus();
            const data = await fetchJSON(API.grabStatus);
            if (data.success && !data.state.running) {
                clearInterval(grabStatusTimer);
                grabStatusTimer = null;
                showToast("抢座任务已结束", "success");
            }
        }, 3000);
    }

    // ---------- 日志 ----------

    async function loadLogs() {
        const lines = document.getElementById("logLines").value || 100;
        const data = await fetchJSON(`${API.logs}?lines=${lines}`);
        if (data.success) {
            document.getElementById("logBox").textContent = data.logs || "暂无日志";
        }
    }

    // ---------- 账号新增/编辑 ----------

    function openAddUserModal() {
        document.getElementById("modalTitle").textContent = "新增账号";
        document.getElementById("modalOriginalUsername").value = "";
        document.getElementById("modalUsername").value = "";
        document.getElementById("modalUsername").disabled = false;
        document.getElementById("modalPassword").value = "";
        document.getElementById("modalMode").value = "3";
        document.getElementById("modalClassrooms").value = "";
        document.getElementById("modalDate").value = "today";
        document.getElementById("modalPushMethod").value = "";
        document.getElementById("modalDdToken").value = "";
        document.getElementById("modalDdSecret").value = "";
        renderSeatRows([]);
        onModeChange();
        document.getElementById("userModal").classList.add("show");
    }

    function openEditUserModal(username) {
        const user = (window._usersCache || []).find((u) => u.username === username);
        if (!user) {
            showToast("账号数据未找到", "error");
            return;
        }
        document.getElementById("modalTitle").textContent = "编辑账号";
        document.getElementById("modalOriginalUsername").value = username;
        document.getElementById("modalUsername").value = user.username || "";
        // 保留学号可编辑（后端已支持学号变更同步 users.yml 与 admin.yml）
        document.getElementById("modalUsername").disabled = false;
        document.getElementById("modalPassword").value = user.password || "";
        document.getElementById("modalMode").value = user.mode || "3";
        document.getElementById("modalClassrooms").value = (user.classrooms_name || []).join("\n");
        document.getElementById("modalDate").value = user.date || "today";
        document.getElementById("modalPushMethod").value = user.push_method || "";
        document.getElementById("modalDdToken").value = user.dd_bot_token || "";
        document.getElementById("modalDdSecret").value = user.dd_bot_secret || "";
        renderSeatRows(user.seat_id || []);
        onModeChange();
        document.getElementById("userModal").classList.add("show");
    }

    function closeModal() {
        document.getElementById("userModal").classList.remove("show");
    }

    function onModeChange() {
        const mode = document.getElementById("modalMode").value;
        const group = document.getElementById("seatIdGroup");
        const hint = document.getElementById("seatHint");
        if (mode === "2" || mode === "3") {
            group.classList.add("hidden");
            return;
        }
        group.classList.remove("hidden");
        if (mode === "1") {
            hint.textContent = "格式：[起始号, 结束号]，如 [7480, 7519]";
        } else if (mode === "4") {
            hint.textContent = "格式：座位号（单个数字），按优先级从高到低";
        }
        // 重新渲染以匹配当前模式的输入控件
        const current = collectSeatRows();
        renderSeatRows(current);
    }

    function renderSeatRows(seatId) {
        const container = document.getElementById("seatIdContainer");
        const mode = document.getElementById("modalMode").value;
        container.innerHTML = "";
        if (!seatId || seatId.length === 0) {
            addSeatRow();
            return;
        }
        seatId.forEach((s) => {
            if (mode === "1") {
                // 范围对 [start, end]
                const start = Array.isArray(s) ? s[0] : "";
                const end = Array.isArray(s) ? s[1] : "";
                container.insertAdjacentHTML("beforeend", `
                    <div class="seat-row">
                        <input type="number" placeholder="起始号" value="${escapeHTML(String(start))}" data-seat-start>
                        <span>-</span>
                        <input type="number" placeholder="结束号" value="${escapeHTML(String(end))}" data-seat-end>
                        <button class="btn-danger btn-sm" type="button" onclick="removeSeatRow(this)">删除</button>
                    </div>
                `);
            } else if (mode === "4") {
                // 单个座位号
                const val = Array.isArray(s) ? s[0] : s;
                container.insertAdjacentHTML("beforeend", `
                    <div class="seat-row">
                        <input type="number" placeholder="座位号" value="${escapeHTML(String(val))}" data-seat-single>
                        <button class="btn-danger btn-sm" type="button" onclick="removeSeatRow(this)">删除</button>
                    </div>
                `);
            }
        });
    }

    function addSeatRow() {
        const mode = document.getElementById("modalMode").value;
        const container = document.getElementById("seatIdContainer");
        if (mode === "1") {
            container.insertAdjacentHTML("beforeend", `
                <div class="seat-row">
                    <input type="number" placeholder="起始号" data-seat-start>
                    <span>-</span>
                    <input type="number" placeholder="结束号" data-seat-end>
                    <button class="btn-danger btn-sm" type="button" onclick="removeSeatRow(this)">删除</button>
                </div>
            `);
        } else if (mode === "4") {
            container.insertAdjacentHTML("beforeend", `
                <div class="seat-row">
                    <input type="number" placeholder="座位号" data-seat-single>
                    <button class="btn-danger btn-sm" type="button" onclick="removeSeatRow(this)">删除</button>
                </div>
            `);
        }
    }

    function removeSeatRow(btn) {
        btn.closest(".seat-row").remove();
    }

    function collectSeatRows() {
        const mode = document.getElementById("modalMode").value;
        const rows = document.querySelectorAll("#seatIdContainer .seat-row");
        const result = [];
        rows.forEach((row) => {
            if (mode === "1") {
                const start = row.querySelector("[data-seat-start]").value;
                const end = row.querySelector("[data-seat-end]").value;
                if (start && end) {
                    result.push([parseInt(start, 10), parseInt(end, 10)]);
                }
            } else if (mode === "4") {
                const val = row.querySelector("[data-seat-single]").value;
                if (val) result.push([parseInt(val, 10)]);
            }
        });
        return result;
    }

    async function saveUser() {
        const originalUsername = document.getElementById("modalOriginalUsername").value;
        const username = document.getElementById("modalUsername").value.trim();
        const password = document.getElementById("modalPassword").value;
        const mode = document.getElementById("modalMode").value;
        const classrooms = document.getElementById("modalClassrooms").value
            .split("\n").map((s) => s.trim()).filter(Boolean);
        const date = document.getElementById("modalDate").value;
        const pushMethod = document.getElementById("modalPushMethod").value;
        const ddToken = document.getElementById("modalDdToken").value;
        const ddSecret = document.getElementById("modalDdSecret").value;
        const seatId = collectSeatRows();

        if (!username) { showToast("学号不能为空", "error"); return; }
        if (!password) { showToast("密码不能为空", "error"); return; }

        // 编辑时若修改了学号，二次确认
        if (originalUsername && originalUsername !== username) {
            if (!confirm(`确认将学号从 ${originalUsername} 修改为 ${username}？\n这会同步更新抢座顺序中的引用。`)) return;
        }

        const payload = {
            username, password, mode, seat_id: seatId,
            classrooms_name: classrooms, date,
            push_method: pushMethod,
            dd_bot_token: ddToken, dd_bot_secret: ddSecret,
        };

        let data;
        if (originalUsername) {
            // 编辑：URL 用原学号定位，body 中携带新学号
            data = await fetchJSON(`${API.users}/${encodeURIComponent(originalUsername)}`, {
                method: "PUT", body: payload,
            });
        } else {
            data = await fetchJSON(API.users, { method: "POST", body: payload });
        }

        if (data.success) {
            showToast("保存成功", "success");
            closeModal();
            await loadUsers();
        } else {
            showToast(data.error || "保存失败", "error");
        }
    }

    async function deleteUser(username) {
        if (!confirm(`确认删除账号 ${username}？此操作不可恢复。`)) return;
        const data = await fetchJSON(`${API.users}/${encodeURIComponent(username)}`, { method: "DELETE" });
        if (data.success) {
            showToast("删除成功", "success");
            await loadUsers();
        } else {
            showToast(data.error || "删除失败", "error");
        }
    }

    // ---------- 初始化 ----------

    async function init() {
        // 检查是否已登录（通过尝试加载用户列表）
        const data = await fetchJSON(API.users);
        if (data.success) {
            await showMainView();
        } else {
            showLoginView();
        }
    }

    // 暴露给 HTML onclick 使用
    window.login = login;
    window.logout = logout;
    window.triggerGrab = triggerGrab;
    window.refreshGrabStatus = refreshGrabStatus;
    window.loadLogs = loadLogs;
    window.saveOrder = saveOrder;
    window.moveOrder = moveOrder;
    window.openAddUserModal = openAddUserModal;
    window.openEditUserModal = openEditUserModal;
    window.closeModal = closeModal;
    window.saveUser = saveUser;
    window.deleteUser = deleteUser;
    window.onModeChange = onModeChange;
    window.addSeatRow = addSeatRow;
    window.removeSeatRow = removeSeatRow;
    window.togglePasswordVisibility = togglePasswordVisibility;

    document.addEventListener("DOMContentLoaded", init);
    // 回车键登录
    document.getElementById("loginPassword").addEventListener("keypress", (e) => {
        if (e.key === "Enter") login();
    });
})();
