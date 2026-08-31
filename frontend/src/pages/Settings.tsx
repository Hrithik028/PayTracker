import { HardDrive, Network, Save, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, LoadingState } from "../components/PageState";
import { api } from "../services/api";

type SettingsData = {
  tesseract_cmd: string;
  currency: string;
  time_format: string;
  backup_location: string;
  retain_uploads: boolean;
  max_upload_mb: number;
};

export function Settings() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const load = () => api.getSettings().then((value) => setSettings(value as unknown as SettingsData)).catch((reason) => setError(reason.message));
  useEffect(() => { void load(); }, []);
  if (error && !settings) return <ErrorState message={error} retry={load} />;
  if (!settings) return <LoadingState label="Loading local settings…" />;
  const set = <K extends keyof SettingsData>(key: K, value: SettingsData[K]) => setSettings({ ...settings, [key]: value });
  const save = async () => {
    setSaving(true); setError(""); setSaved(false);
    try { await api.updateSettings(settings); setSaved(true); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save settings"); }
    finally { setSaving(false); }
  };
  return (
    <>
      <PageHeader title="Settings" description="Configuration is stored locally. Storage paths remain inside D:\\Project\\PayTracker." />
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <section className="card">
          <h2 className="flex items-center gap-2 text-lg font-bold text-navy-950"><HardDrive size={20} /> Local processing</h2>
          <div className="mt-5 space-y-4">
            <label><span className="label">Tesseract executable location</span><input className="input" value={settings.tesseract_cmd} onChange={(event) => set("tesseract_cmd", event.target.value)} placeholder="C:\Program Files\Tesseract-OCR\tesseract.exe" /><span className="mt-1 block text-xs text-slate-500">Leave blank if tesseract.exe is on PATH.</span></label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label><span className="label">Currency</span><select className="input" value={settings.currency} onChange={(event) => set("currency", event.target.value)}><option>AUD</option></select></label>
              <label><span className="label">Time format</span><select className="input" value={settings.time_format} onChange={(event) => set("time_format", event.target.value)}><option value="24h">24-hour</option><option value="12h">12-hour</option></select></label>
              <label><span className="label">Maximum upload size (MB)</span><input className="input" type="number" min="1" max="100" value={settings.max_upload_mb} onChange={(event) => set("max_upload_mb", Number(event.target.value))} /></label>
              <label><span className="label">Backup folder</span><input className="input" value={settings.backup_location} onChange={(event) => set("backup_location", event.target.value)} /><span className="mt-1 block text-xs text-slate-500">Must remain inside the project.</span></label>
            </div>
            <label className="flex min-h-12 items-center gap-3 rounded-xl border border-slate-200 p-3"><input type="checkbox" className="h-5 w-5 accent-blue-600" checked={settings.retain_uploads} onChange={(event) => set("retain_uploads", event.target.checked)} /><span><span className="block text-sm font-semibold">Retain generated upload copies</span><span className="text-xs text-slate-500">When disabled, copies remain available during review and are removed after confirmation. Your original source files are never deleted. Changing this does not remove existing copies.</span></span></label>
          </div>
          {error && <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          {saved && <p className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm font-medium text-emerald-700">Settings saved locally.</p>}
          <button className="btn-primary mt-5" disabled={saving} onClick={save}><Save size={19} /> {saving ? "Saving…" : "Save settings"}</button>
        </section>
        <div className="space-y-6">
          <section className="card">
            <h2 className="flex items-center gap-2 text-lg font-bold text-navy-950"><Network size={20} /> Phone access</h2>
            <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-600">
              <li>Connect your laptop and phone to the same trusted private Wi-Fi.</li>
              <li>Run <code className="rounded bg-slate-100 px-1.5 py-0.5">.\start-paytracker.ps1 -Lan</code>.</li>
              <li>Allow private-network access if Windows Firewall asks.</li>
              <li>Open the printed private IP URL on your phone.</li>
            </ol>
            <p className="mt-4 rounded-xl bg-blue-50 p-3 text-sm text-blue-900">Your laptop must stay on and PayTracker must keep running.</p>
          </section>
          <section className="card border-amber-200 bg-amber-50">
            <h2 className="flex items-center gap-2 font-bold text-amber-900"><ShieldAlert size={20} /> Trusted networks only</h2>
            <p className="mt-2 text-sm leading-6 text-amber-800">LAN mode has no user login in this local-first version. Anyone on the same network who knows the address may be able to open the app. Never use it on public Wi-Fi and do not configure internet port forwarding.</p>
          </section>
        </div>
      </div>
    </>
  );
}
