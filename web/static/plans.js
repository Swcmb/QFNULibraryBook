let currentPlan = null;

function openBuyModal(btn) {
    currentPlan = {
        id: btn.dataset.planId,
        name: btn.dataset.planName,
        price: parseFloat(btn.dataset.planPrice)
    };
    
    document.getElementById('planInfo').textContent = `您选择了：${currentPlan.name} (${currentPlan.price}元/月)`;
    document.getElementById('modalError').classList.remove('show');
    document.getElementById('activationCode').value = '';
    
    fetch('/plans/api/status')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('modalUsername').value = '';
                document.getElementById('loginRequired').style.display = 'none';
                document.getElementById('purchaseForm').style.display = 'block';
                document.getElementById('modalUsername').value = '';
            } else {
                document.getElementById('loginRequired').style.display = 'block';
                document.getElementById('purchaseForm').style.display = 'none';
            }
        })
        .catch(() => {
            document.getElementById('loginRequired').style.display = 'block';
            document.getElementById('purchaseForm').style.display = 'none';
        });
    
    document.getElementById('buyModal').classList.add('show');
}

function closeModal() {
    document.getElementById('buyModal').classList.remove('show');
    currentPlan = null;
}

function activateSubscription() {
    const code = document.getElementById('activationCode').value.trim();
    const btn = document.getElementById('activateBtn');
    
    if (!code) {
        showError('请输入激活码');
        return;
    }
    
    if (!currentPlan) {
        showError('请选择套餐');
        return;
    }
    
    btn.disabled = true;
    btn.textContent = '激活中...';
    
    fetch('/plans/api/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            activation_code: code,
            plan_id: currentPlan.id
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showSuccess(data);
        } else {
            showError(data.error || '激活失败');
        }
    })
    .catch(() => {
        showError('网络请求失败，请重试');
    })
    .finally(() => {
        btn.disabled = false;
        btn.textContent = '立即激活';
    });
}

function showError(msg) {
    const errorEl = document.getElementById('modalError');
    errorEl.textContent = msg;
    errorEl.classList.add('show');
}

function showSuccess(data) {
    const content = document.getElementById('modalContent');
    content.innerHTML = `
        <div class="success-icon">✓</div>
        <div class="success-info">
            <h3>激活成功！</h3>
            <p>${data.message}</p>
            <p class="expires">到期时间：${data.expires_at}</p>
        </div>
        <div class="modal-actions" style="margin-top:20px;">
            <button class="primary" onclick="closeModal(); window.location.href='/ '">返回首页</button>
        </div>
    `;
}

document.getElementById('buyModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeModal();
    }
});

document.getElementById('activationCode').addEventListener('keyup', function(e) {
    if (e.key === 'Enter') {
        activateSubscription();
    }
});