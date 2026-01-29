// 时间工具

// 格式化时间戳为 ISO 8601 格式，包含时区偏移，不使用 "Z" 而是始终包含 "+08:00" 这样的格式
export const formatTimestamp = () => {
  const now = new Date();
  const offset = -now.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const pad = (n: number) => `${Math.floor(Math.abs(n))}`.padStart(2, "0");
  const hours = pad(offset / 60);
  const minutes = pad(offset % 60);
  return now.toISOString().replace("Z", `${sign}${hours}:${minutes}`);
};

export const newDate = () => formatTimestamp();
