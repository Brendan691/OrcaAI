/**
 * 小鲸OrcaAI v0.2.0 — Popup 逻辑 (Chrome + Edge)
 */

const pageTitle = document.getElementById('pageTitle');
const pageUrl = document.getElementById('pageUrl');
const saveBtn = document.getElementById('saveBtn');
const saveStatus = document.getElementById('saveStatus');
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const apiUrlInput = document.getElementById('apiUrl');
const searchToggle = document.getElementById('searchInternet');

let currentTab = null;
let apiBaseUrl = 'http://localhost:8000';

async function init() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTab = tabs[0];

  if (currentTab) {
    pageTitle.textContent = currentTab.title || '未知页面';
    pageUrl.textContent = currentTab.url || '';
  }

  const stored = await chrome.storage.local.get(['apiUrl', 'searchInternet']);
  if (stored.apiUrl) {
    apiBaseUrl = stored.apiUrl;
    apiUrlInput.value = apiBaseUrl;
  }
  if (stored.searchInternet !== undefined) {
    searchToggle.checked = stored.searchInternet;
  }

  apiUrlInput.addEventListener('change', async () => {
    apiBaseUrl = apiUrlInput.value.trim() || 'http://localhost:8000';
    await chrome.storage.local.set({ apiUrl: apiBaseUrl });
  });

  searchToggle.addEventListener('change', async () => {
    await chrome.storage.local.set({ searchInternet: searchToggle.checked });
  });
}

async function saveCurrentPage() {
  if (!currentTab || !currentTab.url) {
    showStatus('无法获取页面信息', 'error');
    return;
  }
  if (currentTab.url.startsWith('chrome://') || currentTab.url.startsWith('edge://') || currentTab.url.startsWith('chrome-extension://')) {
    showStatus('无法保存浏览器内部页面', 'error');
    return;
  }

  saveBtn.disabled = true;
  showStatus('正在解析页面并保存...', 'loading');

  try {
    const response = await fetch(`${apiBaseUrl}/api/documents/upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: currentTab.url, title: currentTab.title }),
    });

    const result = await response.json();

    if (result.success) {
      const tags = result.tags || {};
      const tagStr = [
        ...(tags.business_type || []),
        ...(tags.geographic_region || []),
        ...(tags.topic_category || []),
        ...(tags.event_nature || []),
      ].slice(0, 3).join('、') || '通用';

      showStatus(`✅ 保存成功！自动标签：${tagStr}`, 'success');
    } else {
      showStatus(`❌ 保存失败：${result.message}`, 'error');
    }
  } catch (error) {
    showStatus(`❌ 网络错误：${error.message}`, 'error');
  } finally {
    saveBtn.disabled = false;
  }
}

function showStatus(message, type) {
  saveStatus.textContent = message;
  saveStatus.className = 'save-status ' + type;
  if (type !== 'loading') {
    setTimeout(() => {
      saveStatus.textContent = '';
      saveStatus.className = 'save-status';
    }, 5000);
  }
}

function addMessage(content, role) {
  const div = document.createElement('div');
  div.className = `message ${role}-message`;
  div.textContent = content;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendMessage() {
  const message = chatInput.value.trim();
  if (!message) return;

  addMessage(message, 'user');
  chatInput.value = '';

  const loadingDiv = document.createElement('div');
  loadingDiv.className = 'message assistant-message loading';
  loadingDiv.textContent = '小鲸正在思考...';
  chatMessages.appendChild(loadingDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const response = await fetch(`${apiBaseUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        search_internet: searchToggle.checked,
      }),
    });

    const result = await response.json();
    chatMessages.removeChild(loadingDiv);

    let answer = result.answer;
    if (result.sources && result.sources.length > 0) {
      answer += '\n\n📚 参考来源：';
      result.sources.forEach((src, i) => {
        answer += `\n${i + 1}. ${src.title}`;
      });
    }
    addMessage(answer, 'assistant');
  } catch (error) {
    chatMessages.removeChild(loadingDiv);
    addMessage(`请求失败：${error.message}，请检查后端服务是否运行`, 'assistant');
  }
}

saveBtn.addEventListener('click', saveCurrentPage);
sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') sendMessage();
});

init();
