
// ==================== 认证相关 ====================
let isLoggedIn = false;
let currentUsername = "";

// 全局消息提示
function showMessage(message, type = 'info', duration = 3000) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  // 图标映射
  let icon = '';
  if (type === 'success') icon = '✅';
  else if (type === 'error') icon = '❌';
  else if (type === 'warning') icon = '⚠️';
  else icon = 'ℹ️';

  toast.innerHTML = `<span style="font-size: 1.2em;">${icon}</span> <span>${message}</span>`;

  container.appendChild(toast);

  // 自动移除
  setTimeout(() => {
    toast.classList.add('hiding');
    toast.addEventListener('animationend', () => {
      toast.remove();
    });
  }, duration);
}

// 检查登录状态
async function checkLoginStatus() {
  try {
    const response = await fetch("/api/v1/auth/status", {
      credentials: "include",
    });
    const data = await response.json();

    if (data.success && data.logged_in) {
      isLoggedIn = true;
      currentUsername = data.username;
      showUserInfo();
      hideLoginOverlay();
    } else {
      isLoggedIn = false;
      showLoginOverlay();
      hideUserInfo();
    }
  } catch (error) {
    console.error("检查登录状态失败:", error);
    showLoginOverlay();
    hideUserInfo();
  }
}

// 处理登录
async function handleLogin(event) {
  event.preventDefault();
  const username = document.getElementById("loginUsername").value;
  const password = document.getElementById("loginPassword").value;

  try {
    const response = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (data.success) {
      showLoginMessage("登录成功！", true);
      setTimeout(() => {
        checkLoginStatus();
      }, 500);
    } else {
      showLoginMessage(data.error || "登录失败", false);
    }
  } catch (error) {
    showLoginMessage("登录失败: " + error.message, false);
  }
}

// 处理登出
async function handleLogout() {
  if (!confirm("确定要登出吗？")) {
    return;
  }

  try {
    const response = await fetch("/api/v1/auth/logout", {
      method: "POST",
      credentials: "include",
    });

    const data = await response.json();

    if (data.success) {
      isLoggedIn = false;
      currentUsername = "";
      showLoginOverlay();
      hideUserInfo();
    }
  } catch (error) {
    console.error("登出失败:", error);
  }
}

// 显示登录消息
function showLoginMessage(message, isSuccess) {
  showMessage(message, isSuccess ? "success" : "error");
}

// 显示/隐藏登录界面
function showLoginOverlay() {
  document.getElementById("loginOverlay").classList.remove("hidden");
}

function hideLoginOverlay() {
  document.getElementById("loginOverlay").classList.add("hidden");
}

// 显示/隐藏用户信息
function showUserInfo() {
  const userInfoEl = document.getElementById("userInfo");
  const usernameEl = document.getElementById("displayUsername");
  usernameEl.textContent = currentUsername;
  userInfoEl.classList.remove("hidden");
}

function hideUserInfo() {
  document.getElementById("userInfo").classList.add("hidden");
}

// 处理API错误（401未授权）
function handleApiError(response, data) {
  if (response.status === 401) {
    alert("会话已过期，请重新登录");
    isLoggedIn = false;
    showLoginOverlay();
    hideUserInfo();
    return true;
  }
  return false;
}

// ==================== 配置相关 ====================

let CONFIG_SECTIONS = {}; // 配置字段分组
let currentConfig = {}; // 嵌套格式: {section: {key: value}}
let configFields = {}; // full_key -> field信息

// 切换标签页
function switchTab(tabName) {
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.remove("active"));
  document
    .querySelectorAll(".tab-content")
    .forEach((c) => c.classList.remove("active"));

  const tabIndex =
    tabName === "system" ? 1 : tabName === "config" ? 2 : 3;
  document
    .querySelector(`.tab:nth-child(${tabIndex})`)
    .classList.add("active");
  document.getElementById(`${tabName}-tab`).classList.add("active");

  if (tabName === "config") {
    loadConfig();
  } else if (tabName === "system") {
    scanWifi();
    loadVolume();
    loadLogList();
  } else if (tabName === "sdk") {
    loadSdkConfig();
    loadMotionConfig();
  }
}

// 折叠/展开功能
function toggleCollapse(section) {
  const content = document.getElementById(`${section}-content`);
  const icon = document.getElementById(`${section}-icon`);

  if (content.classList.contains("expanded")) {
    content.classList.remove("expanded");
    icon.classList.remove("expanded");
  } else {
    content.classList.add("expanded");
    icon.classList.add("expanded");
  }
}

// ==================== 音量控制功能 ====================

let currentVolume = 50;
let isMuted = false;

function updateVolumeDisplay(value) {
  currentVolume = parseInt(value);
  document.getElementById("volumeValue").textContent =
    `${currentVolume}%`;
}

async function loadVolume() {
  try {
    const response = await fetch("/api/v1/volume");
    const data = await response.json();

    if (data.success && data.data) {
      currentVolume = data.data.volume || 50;
      isMuted = data.data.muted || false;

      document.getElementById("volumeSlider").value = currentVolume;
      document.getElementById("volumeValue").textContent =
        `${currentVolume}%`;
      updateMuteButton();
    } else {
      showVolumeMessage(
        "获取音量失败: " + (data.error || "未知错误"),
        "error",
      );
    }
  } catch (error) {
    showVolumeMessage("获取音量失败: " + error.message, "error");
  }
}

async function setVolume() {
  try {
    const response = await fetch("/api/v1/volume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ volume: currentVolume }),
    });

    const data = await response.json();

    if (handleApiError(response, data)) return;

    if (data.success) {
      showVolumeMessage(`音量已设置为 ${currentVolume}%`, "success");
    } else {
      showVolumeMessage(
        "设置音量失败: " + (data.error || "未知错误"),
        "error",
      );
    }
  } catch (error) {
    showVolumeMessage("设置音量失败: " + error.message, "error");
  }
}

async function toggleMute() {
  isMuted = !isMuted;

  try {
    const response = await fetch("/api/v1/volume/mute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ mute: isMuted }),
    });

    const data = await response.json();

    if (handleApiError(response, data)) {
      isMuted = !isMuted; // 回滚
      return;
    }

    if (data.success) {
      updateMuteButton();
      showVolumeMessage(isMuted ? "已静音" : "已取消静音", "success");
    } else {
      isMuted = !isMuted; // 回滚
      showVolumeMessage(
        "设置静音失败: " + (data.error || "未知错误"),
        "error",
      );
    }
  } catch (error) {
    isMuted = !isMuted; // 回滚
    showVolumeMessage("设置静音失败: " + error.message, "error");
  }
}

function updateMuteButton() {
  const btn = document.getElementById("muteBtn");
  if (isMuted) {
    btn.textContent = "🔇";
    btn.classList.add("secondary");
  } else {
    btn.textContent = "🔊";
    btn.classList.remove("secondary");
  }
}

function showVolumeMessage(text, type) {
  showMessage(text, type);
}

// ==================== WiFi功能 ====================

let currentWifiList = [];
let groupBySSID = true;

function scanWifi() {
  const wifiListDiv = document.getElementById("wifiList");
  const refreshBtn = document.getElementById("refreshWifi");

  wifiListDiv.innerHTML = '<div class="loading">正在扫描WiFi...</div>';
  refreshBtn.disabled = true;
  refreshBtn.textContent = "扫描中...";

  return fetch("/api/v1/wifi/scan")
    .then((response) => response.json())
    .then((data) => {
      if (data.success && data.networks) {
        currentWifiList = data.networks;
        renderWifiList();
      } else {
        wifiListDiv.innerHTML =
          '<div class="loading">未找到可用WiFi网络</div>';
      }
    })
    .catch((error) => {
      wifiListDiv.innerHTML = `<div class="loading" style="color: #f44336;">扫描失败: ${error.message}</div>`;
    })
    .finally(() => {
      refreshBtn.disabled = false;
      refreshBtn.textContent = "刷新";
    });
}

function renderWifiList() {
  const wifiListDiv = document.getElementById("wifiList");

  if (!currentWifiList || currentWifiList.length === 0) {
    wifiListDiv.innerHTML = '<div class="loading">未找到可用WiFi网络</div>';
    return;
  }

  let displayList = [...currentWifiList];

  if (groupBySSID) {
    const groups = {};
    displayList.forEach((net) => {
      // 如果没有这个SSID或者当前信号更强且未连接（优先保留已连接的）
      if (!groups[net.ssid]) {
        groups[net.ssid] = net;
      } else {
        const existing = groups[net.ssid];
        // 如果现有的是已连接的，不替换
        if (existing.in_use) return;
        // 如果新的是已连接的，替换
        if (net.in_use) {
          groups[net.ssid] = net;
          return;
        }
        // 比较信号强度
        if (parseInt(net.signal) > parseInt(existing.signal)) {
          groups[net.ssid] = net;
        }
      }
    });
    displayList = Object.values(groups);
  }

  // 排序：已连接优先，然后按信号强度降序
  displayList.sort((a, b) => {
    if (a.in_use) return -1;
    if (b.in_use) return 1;
    return parseInt(b.signal) - parseInt(a.signal);
  });

  wifiListDiv.innerHTML = "";
  displayList.forEach((network) => {
    const item = document.createElement("div");
    item.className = "wifi-item" + (network.in_use ? " connected" : "");
    item.onclick = () => selectWifi(network.ssid, item);

    const badge = network.in_use
      ? '<span class="badge connected">已连接</span>'
      : "";

    // 如果是聚合模式，可能不显示具体的BSSID信息（虽然原API也不返回BSSID，只返回SSID/CHAN/SIGNAL/SECURITY）
    // 这里我们保持原样显示
    item.innerHTML = `
      <div>
          <strong>${network.ssid}</strong>${badge}
          <br><small style="color: #888;">信号: ${network.signal}% | 频道: ${network.channel} | ${network.security}</small>
      </div>
    `;
    wifiListDiv.appendChild(item);
  });
}

function toggleWifiGrouping(checkbox) {
  groupBySSID = checkbox.checked;
  renderWifiList();
}

function selectWifi(ssid, element) {
  document.getElementById("ssid").value = ssid;
  document
    .querySelectorAll(".wifi-item")
    .forEach((item) => item.classList.remove("selected"));
  element.classList.add("selected");
}

function connectWifi(e) {
  e.preventDefault();
  const ssid = document.getElementById("ssid").value;
  const password = document.getElementById("password").value;

  showMessage("正在连接WiFi...", "info");

  fetch("/api/v1/wifi/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ ssid, password }),
  })
    .then((response) => {
      if (response.status === 401) {
        alert("会话已过期，请重新登录");
        isLoggedIn = false;
        showLoginOverlay();
        hideUserInfo();
        return Promise.reject("未授权");
      }
      return response.json();
    })
    .then((data) => {
      if (data.success) {
        showMessage("WiFi连接成功！", "success");
        setTimeout(() => scanWifi(), 2000);
      } else {
        showMessage("WiFi连接失败：" + (data.error || "未知错误"), "error");
      }
    })
    .catch((error) => {
      showMessage("请求失败：" + error.message, "error");
    });
}

// ==================== 日志功能 ====================

function formatDateTimeLocal(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hour = String(date.getHours()).padStart(2, "0");
  const minute = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

function initLogTimeRange() {
  const end = new Date();
  const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
  document.getElementById("logStartTime").value = formatDateTimeLocal(start);
  document.getElementById("logEndTime").value = formatDateTimeLocal(end);
}

function formatFileSize(bytes) {
  const size = Number(bytes) || 0;
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(2)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}

function showLogMessage(text, type) {
  showMessage(text, type);
}

function renderLogAppOptions(apps, selectedValue) {
  const select = document.getElementById("logAppSelect");
  const current = selectedValue ?? select.value;

  let html = '<option value="">全部应用</option>';
  apps.forEach((app) => {
    const selectedAttr = app === current ? "selected" : "";
    html += `<option value="${app}" ${selectedAttr}>${app}</option>`;
  });
  select.innerHTML = html;
}

function renderLogList(logs) {
  const listDiv = document.getElementById("logList");
  if (!logs || logs.length === 0) {
    listDiv.innerHTML = '<div class="loading">暂无日志文件</div>';
    return;
  }

  const rows = logs
    .map(
      (log) => `
      <tr>
        <td>${log.app_name || "-"}</td>
        <td>${log.date_folder || "-"}</td>
        <td>${log.file_name}</td>
        <td>${formatFileSize(log.size_bytes)}</td>
        <td>${new Date(log.modified_time).toLocaleString()}</td>
      </tr>`,
    )
    .join("");

  listDiv.innerHTML = `
    <table class="log-table">
      <thead>
        <tr>
          <th>应用</th>
          <th>日期目录</th>
          <th>文件名</th>
          <th>大小</th>
          <th>最后修改时间</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

async function loadLogList() {
  const listDiv = document.getElementById("logList");
  listDiv.innerHTML = '<div class="loading">正在加载日志列表...</div>';

  const appName = document.getElementById("logAppSelect").value.trim();
  const params = new URLSearchParams();
  if (appName) {
    params.set("app_name", appName);
  }
  const url = params.toString()
    ? `/api/v1/logs?${params.toString()}`
    : "/api/v1/logs";

  try {
    const response = await fetch(url, { credentials: "include" });
    const data = await response.json();

    if (handleApiError(response, data)) return;
    if (!data.success) {
      throw new Error(data.error || "获取日志列表失败");
    }

    renderLogAppOptions(data.apps || [], appName);
    renderLogList(data.logs || []);
  } catch (error) {
    listDiv.innerHTML = `<div class="loading" style="color: #f44336;">${error.message}</div>`;
  }
}

function getFilenameFromDisposition(disposition) {
  if (!disposition) {
    return "logs.zip";
  }
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match && utf8Match[1]) {
    return decodeURIComponent(utf8Match[1]);
  }
  const asciiMatch = disposition.match(/filename="?([^";]+)"?/i);
  if (asciiMatch && asciiMatch[1]) {
    return asciiMatch[1];
  }
  return "logs.zip";
}

async function downloadLogsByTime() {
  const startInput = document.getElementById("logStartTime").value;
  const endInput = document.getElementById("logEndTime").value;
  const appName = document.getElementById("logAppSelect").value.trim();

  if (!startInput || !endInput) {
    showLogMessage("请选择开始和结束时间", "error");
    return;
  }

  const startDate = new Date(startInput);
  const endDate = new Date(endInput);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
    showLogMessage("时间格式无效", "error");
    return;
  }
  if (startDate > endDate) {
    showLogMessage("开始时间不能晚于结束时间", "error");
    return;
  }

  const params = new URLSearchParams({
    start_time: startDate.toISOString(),
    end_time: endDate.toISOString(),
  });
  if (appName) {
    params.set("app_name", appName);
  }

  showLogMessage("正在打包日志，请稍候...", "success");

  try {
    const response = await fetch(`/api/v1/logs/download?${params.toString()}`, {
      credentials: "include",
    });

    if (!response.ok) {
      let errorMessage = `下载失败 (${response.status})`;
      try {
        const errorData = await response.json();
        if (handleApiError(response, errorData)) return;
        errorMessage =
          errorData?.error ||
          errorData?.detail?.error ||
          errorData?.message ||
          errorMessage;
      } catch (_e) {
        // 忽略JSON解析失败，使用默认错误信息
      }
      throw new Error(errorMessage);
    }

    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition");
    const fileName = getFilenameFromDisposition(disposition);

    const link = document.createElement("a");
    const objectUrl = URL.createObjectURL(blob);
    link.href = objectUrl;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);

    showLogMessage("日志打包下载成功", "success");
  } catch (error) {
    showLogMessage(error.message || "下载失败", "error");
  }
}

// ==================== 配置功能 ====================

async function loadConfig() {
  const container = document.getElementById("configContainer");
  container.innerHTML = '<div class="loading">正在加载配置...</div>';

  try {
    // 并行加载配置、字段信息和分组信息
    const [configRes, fieldsRes, sectionsRes] = await Promise.all([
      fetch("/api/v1/config"),
      fetch("/api/v1/config/fields"),
      fetch("/api/v1/config/sections"),
    ]);

    const configData = await configRes.json();
    const fieldsData = await fieldsRes.json();
    const sectionsData = await sectionsRes.json();

    if (configData.success && fieldsData.success && sectionsData.success) {
      currentConfig = configData.config; // 嵌套格式
      configFields = {};
      fieldsData.fields.forEach((f) => (configFields[f.full_key] = f));
      // 将数组转换为对象格式供 renderConfig 使用
      CONFIG_SECTIONS = {};
      sectionsData.sections.forEach((s) => {
        CONFIG_SECTIONS[s.section] = { title: s.title, keys: s.keys };
      });
      renderConfig();
    } else {
      container.innerHTML =
        '<div class="loading" style="color: #f44336;">加载配置失败</div>';
    }
  } catch (error) {
    container.innerHTML = `<div class="loading" style="color: #f44336;">加载失败: ${error.message}</div>`;
  }
}

function renderConfig() {
  const container = document.getElementById("configContainer");
  let html = "";

  for (const [section, group] of Object.entries(CONFIG_SECTIONS)) {
    html += `<div class="config-section">
                    <div class="config-section-title">${group.title} [${section}]</div>
                    <div class="config-grid">`;

    for (const key of group.keys) {
      const fullKey = `${section}.${key}`;
      const field = configFields[fullKey] || {
        description: key,
        type: "string",
        readonly: false,
      };
      const sectionConfig = currentConfig[section] || {};
      const value = sectionConfig[key] ?? "";

      const readonlyBadge = field.readonly
        ? '<span style="color:#ff9800;font-size:11px;margin-left:6px;">[只读]</span>'
        : "";

      html += `<div class="config-item">
                        <label>
                            ${field.description}${readonlyBadge}
                            <span class="key-name">${key}</span>
                        </label>
                        ${renderInput(section, key, value, field)}
                    </div>`;
    }

    html += "</div></div>";
  }

  container.innerHTML = html;
}

function getInputType(type) {
  switch (type) {
    case "int":
    case "float":
      return "number";
    case "bool":
      return "checkbox";
    default:
      return "text";
  }
}

function renderInput(section, key, value, field) {
  const type = field.type;
  const fullKey = `${section}.${key}`;
  const isReadonly = field.readonly;
  const disabledAttr = isReadonly ? "disabled" : "";
  const readonlyStyle = isReadonly
    ? "background-color: #f5f5f5; color: #888; cursor: not-allowed;"
    : "";

  if (type === "bool") {
    const checked = value ? "checked" : "";
    return `<input type="checkbox" id="config_${fullKey}" data-section="${section}" data-key="${key}" data-type="${type}" ${checked} ${disabledAttr} style="width: auto; margin-top: 10px; ${readonlyStyle}">`;
  }

  if (Array.isArray(field.options) && field.options.length) {
    let html = `<select id="config_${fullKey}" data-section="${section}" data-key="${key}" data-type="${type}" ${disabledAttr} style="${readonlyStyle}">`;
    field.options.forEach((opt) => {
      const selected = value === opt ? "selected" : "";
      html += `<option value="${opt}" ${selected}>${opt}</option>`;
    });
    html += "</select>";
    return html;
  }

  const inputType =
    type === "int" || type === "float" ? "number" : "text";
  const step = type === "float" ? 'step="0.001"' : "";
  return `<input type="${inputType}" id="config_${fullKey}" data-section="${section}" data-key="${key}" data-type="${type}" value="${value}" ${step} ${disabledAttr} style="${readonlyStyle}">`;
}

async function saveConfig() {
  const updates = {};

  // 只收集非只读字段
  document
    .querySelectorAll("[data-section][data-key]:not([disabled])")
    .forEach((input) => {
      const section = input.dataset.section;
      const key = input.dataset.key;
      const type = input.dataset.type;
      let value;

      if (type === "bool") {
        value = input.checked;
      } else if (type === "int") {
        value = parseInt(input.value) || 0;
      } else if (type === "float") {
        value = parseFloat(input.value) || 0;
      } else {
        value = input.value;
      }

      // 构建嵌套结构
      if (!updates[section]) {
        updates[section] = {};
      }
      updates[section][key] = value;
    });

  try {
    const response = await fetch("/api/v1/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(updates),
    });

    const data = await response.json();

    if (handleApiError(response, data)) return;

    if (data.success) {
      showMessage("配置保存成功！", "success");
    } else {
      showMessage(
        "保存失败: " + (data.message || "未知错误"),
        "error",
      );
    }
  } catch (error) {
    showMessage("请求失败: " + error.message, "error");
  }
}

async function resetConfig() {
  if (!confirm("确定要重置所有配置为默认值吗？\n（UUID将保持不变）")) {
    return;
  }

  try {
    const response = await fetch("/api/v1/config/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({}),
    });

    const data = await response.json();

    if (handleApiError(response, data)) return;

    if (data.success) {
      showMessage("配置已重置为默认值！", "success");
      await loadConfig();
    } else {
      showMessage(
        "重置失败: " + (data.message || "未知错误"),
        "error",
      );
    }
  } catch (error) {
    showMessage("请求失败: " + error.message, "error");
  }
}

// ==================== SDK 配置和运控管理功能 ====================

const SDK_API_BASE = "/api/v1/sdk";

// 显示 SDK 相关消息
function showSdkMessage(elementId, message, isSuccess) {
  showMessage(message, isSuccess ? "success" : "error");
}

// 加载 SDK 配置
async function loadSdkConfig() {
  try {
    const response = await fetch(`${SDK_API_BASE}/config`);
    const data = await response.json();

    if (data.success) {
      const config = data.config;
      document.getElementById("sdkCurrentValue").innerHTML =
        `<strong>当前配置:</strong> target_ip=${config.target_ip}, target_port=${config.target_port}`;
      document.getElementById("sdkTargetIp").value = config.target_ip;
      document.getElementById("sdkTargetPort").value = config.target_port;
    } else {
      showSdkMessage("sdkMessage", "加载失败: " + data.error, false);
    }
  } catch (error) {
    showSdkMessage("sdkMessage", "加载失败: " + error.message, false);
  }
}

// 修改 SDK 配置
async function updateSdkConfig() {
  const targetIp = document.getElementById("sdkTargetIp").value.trim();
  const targetPort = parseInt(
    document.getElementById("sdkTargetPort").value,
  );

  if (!targetIp) {
    showSdkMessage("sdkMessage", "请输入目标 IP 地址", false);
    return;
  }

  if (!targetPort || targetPort < 1 || targetPort > 65535) {
    showSdkMessage("sdkMessage", "请输入有效的端口号 (1-65535)", false);
    return;
  }

  try {
    const response = await fetch(`${SDK_API_BASE}/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        target_ip: targetIp,
        target_port: targetPort,
      }),
    });

    const data = await response.json();

    if (handleApiError(response, data)) return;

    showSdkMessage(
      "sdkMessage",
      data.message || data.error,
      data.success,
    );

    if (data.success) {
      loadSdkConfig();
    }
  } catch (error) {
    showSdkMessage("sdkMessage", "修改失败: " + error.message, false);
  }
}

// 重置 SDK 配置
async function resetSdkConfig() {
  if (!confirm("确定要重置 SDK 配置为默认值吗？")) {
    return;
  }

  try {
    const response = await fetch(`${SDK_API_BASE}/config/reset`, {
      method: "POST",
      credentials: "include",
    });

    const data = await response.json();

    if (handleApiError(response, data)) return;

    showSdkMessage(
      "sdkMessage",
      data.message || data.error,
      data.success,
    );

    if (data.success) {
      loadSdkConfig();
    }
  } catch (error) {
    showSdkMessage("sdkMessage", "重置失败: " + error.message, false);
  }
}

// 加载运控配置
async function loadMotionConfig() {
  try {
    const response = await fetch(`${SDK_API_BASE}/motion`);
    const data = await response.json();

    if (data.success) {
      const config = data.config;
      const sdkClientIp = config.sdk_client_ip || "未设置（AP/有线模式）";
      document.getElementById("motionCurrentValue").innerHTML =
        `<strong>当前配置:</strong> SDK_CLIENT_IP=${sdkClientIp}`;
      document.getElementById("motionSdkClientIp").value =
        config.sdk_client_ip || "";
    } else {
      showSdkMessage("motionMessage", "加载失败: " + data.error, false);
    }
  } catch (error) {
    showSdkMessage("motionMessage", "加载失败: " + error.message, false);
  }
}

// 修改运控配置
async function updateMotionConfig() {
  const sdkClientIp = document
    .getElementById("motionSdkClientIp")
    .value.trim();

  try {
    const response = await fetch(`${SDK_API_BASE}/motion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ sdk_client_ip: sdkClientIp }),
    });

    const data = await response.json();

    if (handleApiError(response, data)) return;

    showSdkMessage(
      "motionMessage",
      data.message || data.error,
      data.success,
    );

    if (data.success) {
      loadMotionConfig();
    }
  } catch (error) {
    showSdkMessage("motionMessage", "修改失败: " + error.message, false);
  }
}

// 重置运控配置
async function resetMotionConfig() {
  if (!confirm("确定要重置运控配置吗？这将清除 SDK_CLIENT_IP 设置。")) {
    return;
  }

  try {
    const response = await fetch(`${SDK_API_BASE}/motion/reset`, {
      method: "POST",
      credentials: "include",
    });

    const data = await response.json();

    if (handleApiError(response, data)) return;

    showSdkMessage(
      "motionMessage",
      data.message || data.error,
      data.success,
    );

    if (data.success) {
      loadMotionConfig();
    }
  } catch (error) {
    showSdkMessage("motionMessage", "重置失败: " + error.message, false);
  }
}

// 重启运控服务
async function restartMotion() {
  if (
    !confirm(
      "⚠️ 警告：重启运控前请确保机器狗已经卧倒！\n\n确定要重启运控服务吗？",
    )
  ) {
    return;
  }

  try {
    showMessage("正在重启运控服务，请稍候...", "info");

    const response = await fetch(`${SDK_API_BASE}/motion/restart`, {
      method: "POST",
      credentials: "include",
    });

    const data = await response.json();

    if (handleApiError(response, data)) return;

    showSdkMessage(
      "restartMessage",
      data.message || data.error,
      data.success,
    );
  } catch (error) {
    showSdkMessage("restartMessage", "重启失败: " + error.message, false);
  }
}

// ==================== 遥测状态 ====================
async function loadTelemetry() {
  try {
    const response = await fetch("/api/v1/telemetry", {
      credentials: "include",
    });
    const data = await response.json();
    if (!data.success) return;

    const d = data.data;

    // 在线状态
    const onlineEl = document.getElementById("telemetryOnline");
    onlineEl.textContent = d.online ? "🟢 在线" : "🔴 离线";
    onlineEl.className = "telemetry-item " + (d.online ? "online" : "offline");

    // 电量
    const powerEl = document.getElementById("telemetryPower");
    const power = d.power ?? null;
    powerEl.textContent = power !== null ? `🔋 ${power}%` : "🔋 --";
    powerEl.className =
      "telemetry-item" +
      (power !== null && power <= 20
        ? " danger"
        : power !== null && power <= 50
          ? " warning"
          : "");

    // 温度
    const tempEl = document.getElementById("telemetryTemp");
    const temp = d.temp ?? null;
    tempEl.textContent = temp !== null ? `🌡️ ${temp.toFixed(1)}°C` : "🌡️ --";

    // 设备名
    const devEl = document.getElementById("telemetryDev");
    const devDividerEl = document.getElementById("telemetryDevDivider");
    if (d.dev_name || d.model) {
      devEl.textContent = `🐕 ${d.dev_name || d.model}`;
      devDividerEl.classList.remove("hidden");
    } else {
      devEl.textContent = "";
      devDividerEl.classList.add("hidden");
    }
  } catch (e) {
    // 静默失败
  }
}

// 页面加载时检查登录状态
window.onload = function () {
  checkLoginStatus();
  scanWifi();
  loadVolume();
  initLogTimeRange();
  loadLogList();
  loadTelemetry();
  setInterval(loadTelemetry, 5000);
};

// ==================== 全局快捷键 ====================
document.addEventListener("keydown", function (e) {
  // Ctrl+S (Windows/Linux) 或 Command+S (Mac)
  if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")) {
    e.preventDefault();
    console.log("按下“Ctrl+S”键，触发了保存操作……");

    const activeTab = document.querySelector(".tab-content.active");
    if (!activeTab) return;

    if (activeTab.id === "config-tab") {
      saveConfig();
    } else if (activeTab.id === "sdk-tab") {
      // 在 SDK 页面，尝试保存所有配置
      updateSdkConfig();
      updateMotionConfig();
    } else if (activeTab.id === "system-tab") {
      // 在系统设置页面，保存音量设置
      setVolume();
    }
  }
});
