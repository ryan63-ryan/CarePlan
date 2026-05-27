import { useState, useEffect } from "react";

const initialForm = {
  firstName: "",
  lastName: "",
  mrn: "",
  provider: "",
  npi: "",
  diagnosis: "",
  medication: "",
  additionalDiagnosis: "",
  medicationHistory: "",
  patientRecords: "",
};

const labels = {
  firstName: "Patient First Name",
  lastName: "Patient Last Name",
  mrn: "Patient MRN",
  provider: "Referring Provider",
  npi: "Referring Provider NPI",
  diagnosis: "Primary Diagnosis (ICD-10)",
  medication: "Medication Name",
  additionalDiagnosis: "Additional Diagnoses",
  medicationHistory: "Medication History",
  patientRecords: "Patient Records",
};

const POLL_INTERVAL_MS = 3000;

export default function App() {
  const [form, setForm] = useState(initialForm);
  const [carePlanId, setCarePlanId] = useState(null);
  const [status, setStatus] = useState(null); // pending | processing | completed | failed
  const [carePlan, setCarePlan] = useState("");
  const [error, setError] = useState("");

  const onChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const onSubmit = async (e) => {
    e.preventDefault();
    // 重置上一次的结果, 乐观地标记为 pending 让按钮立刻禁用。
    setError("");
    setCarePlan("");
    setCarePlanId(null);
    setStatus("pending");

    try {
      const res = await fetch("/api/orders/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      setCarePlanId(data.carePlanId); // 拿到 care plan id, 触发下面的轮询
      setStatus(data.status); // 后端此时返回 "pending"
    } catch (err) {
      setError("提交失败, 请稍后重试。");
      setStatus("failed");
    }
  };

  // 轮询: 只要拿到了 carePlanId 就每 3 秒查一次状态, 直到 completed / failed 停止。
  // 依赖 [carePlanId]: 每次新提交拿到新 id 时重新开始; 组件卸载或重新提交时清理旧定时器。
  useEffect(() => {
    if (!carePlanId) return;

    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/careplan/${carePlanId}/status/`);
        if (!res.ok) return; // 比如刚提交时 404, 忽略, 等下一轮
        const data = await res.json();
        setStatus(data.status);

        if (data.status === "completed") {
          setCarePlan(data.content || "");
          clearInterval(timer);
        } else if (data.status === "failed") {
          setError("Care plan 生成失败, 请重试。");
          clearInterval(timer);
        }
      } catch (err) {
        // 网络抖动: 忽略本轮, 等下一次重试
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [carePlanId]);

  // pending / processing 期间算"处理中": 禁用按钮、显示进度提示。
  const isWorking =
    status !== null && status !== "completed" && status !== "failed";

  return (
    <div style={{ maxWidth: 720, margin: "2rem auto", fontFamily: "sans-serif", padding: "0 1rem" }}>
      <h1>Care Plan Generator (MVP)</h1>
      <form onSubmit={onSubmit}>
        {Object.keys(initialForm).map((key) => (
          <div key={key} style={{ marginBottom: 10 }}>
            <label style={{ display: "block", fontSize: 13, marginBottom: 2 }}>
              {labels[key]}
            </label>
            <input
              name={key}
              value={form[key]}
              onChange={onChange}
              style={{ width: "100%", padding: 6, boxSizing: "border-box" }}
            />
          </div>
        ))}
        <button
          type="submit"
          disabled={isWorking}
          style={{ marginTop: 12, padding: "8px 16px", cursor: isWorking ? "wait" : "pointer" }}
        >
          {isWorking ? "Generating..." : "Generate Care Plan"}
        </button>
      </form>

      {isWorking && (
        <p style={{ marginTop: 16, color: "#555" }}>
          Generating care plan... (status: {status})
        </p>
      )}

      {error && (
        <div style={{ marginTop: 16, padding: 12, border: "1px solid #e0a0a0", background: "#fdf0f0", color: "#a00" }}>
          {error}
        </div>
      )}

      {status === "completed" && carePlan && (
        <div
          style={{
            marginTop: 24,
            padding: 16,
            border: "1px solid #ccc",
            whiteSpace: "pre-wrap",
            background: "#fafafa",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Care Plan</h2>
          {carePlan}
        </div>
      )}
    </div>
  );
}
