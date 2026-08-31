import { FileImage, FileText, LockKeyhole, UploadCloud, X } from "lucide-react";
import { type ChangeEvent, type DragEvent, useRef, useState } from "react";
import { PageHeader } from "../components/PageHeader";
import { api } from "../services/api";
import { navigate } from "../services/navigation";

const allowed = [".pdf", ".png", ".jpg", ".jpeg"];
const maxBytes = 20 * 1024 * 1024;

export function NewPayPeriod() {
  const [payslip, setPayslip] = useState<File | null>(null);
  const [timings, setTimings] = useState<File[]>([]);
  const [employer, setEmployer] = useState("");
  const [error, setError] = useState("");
  const [processing, setProcessing] = useState(false);

  const validate = (files: File[]) => {
    for (const file of files) {
      const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
      if (!allowed.includes(extension)) throw new Error(`${file.name}: unsupported file type`);
      if (file.size > maxBytes) throw new Error(`${file.name}: exceeds 20 MB`);
    }
  };
  const pickPayslip = (file?: File) => {
    if (!file) return;
    try { validate([file]); setPayslip(file); setError(""); } catch (reason) { setError((reason as Error).message); }
  };
  const pickTimings = (files: File[]) => {
    try { validate(files); setTimings((current) => [...current, ...files]); setError(""); } catch (reason) { setError((reason as Error).message); }
  };
  const submit = async () => {
    if (!payslip) return setError("Select one payslip before processing.");
    setProcessing(true); setError("");
    const form = new FormData();
    form.append("payslip_file", payslip);
    timings.forEach((file) => form.append("timing_files", file));
    if (employer.trim()) form.append("employer_name", employer.trim());
    try {
      const period = await api.processFiles(form);
      navigate(`/pay-periods/${period.id}/payslip`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Local processing failed");
    } finally { setProcessing(false); }
  };

  return (
    <>
      <PageHeader title="New pay period" description="Add one payslip and any shift screenshots. Processing happens only on this computer." />
      <div className="mb-6 flex gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
        <LockKeyhole className="shrink-0" size={21} />
        <div><p className="font-semibold">Private local processing</p><p className="mt-0.5">Files are not sent to cloud services. If extraction fails, temporary copies are removed and no record is saved. Successful results still require your review and confirmation.</p></div>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <section className="card">
          <h2 className="font-bold text-navy-950">1. Payslip</h2>
          <p className="mt-1 text-sm text-slate-500">PDF, PNG, JPG or JPEG · maximum 20 MB</p>
          <DropZone
            label="Drop your payslip here"
            hint="or choose a file"
            multiple={false}
            icon={<FileText size={32} />}
            onFiles={(files) => pickPayslip(files[0])}
          />
          {payslip && <FileChip file={payslip} remove={() => setPayslip(null)} />}
          <label className="label mt-5" htmlFor="employer">Employer name (optional)</label>
          <input id="employer" className="input" value={employer} onChange={(event) => setEmployer(event.target.value)} placeholder="Helps if OCR cannot identify it" />
        </section>
        <section className="card">
          <h2 className="font-bold text-navy-950">2. Timing screenshots</h2>
          <p className="mt-1 text-sm text-slate-500">Select multiple files or use your phone camera</p>
          <DropZone
            label="Drop timing screenshots here"
            hint="or choose / take photos"
            multiple
            capture
            icon={<FileImage size={32} />}
            onFiles={pickTimings}
          />
          <div className="mt-3 space-y-2">
            {timings.map((file, index) => <FileChip key={`${file.name}-${index}`} file={file} remove={() => setTimings((current) => current.filter((_, itemIndex) => itemIndex !== index))} />)}
          </div>
        </section>
      </div>
      {error && <p className="mt-4 rounded-xl bg-red-50 p-3 text-sm font-medium text-red-700" role="alert">{error}</p>}
      <div className="mt-6 flex justify-end">
        <button className="btn-primary w-full sm:w-auto" disabled={!payslip || processing} onClick={submit}>
          <UploadCloud size={20} /> {processing ? "Processing locally…" : "Process files locally"}
        </button>
      </div>
    </>
  );
}

function DropZone({ label, hint, multiple, capture, icon, onFiles }: { label: string; hint: string; multiple: boolean; capture?: boolean; icon: React.ReactNode; onFiles: (files: File[]) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  const handle = (files: FileList | null) => files && onFiles(Array.from(files));
  return (
    <div
      className="mt-5 grid min-h-48 cursor-pointer place-items-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center hover:border-blue-400 hover:bg-blue-50"
      onClick={() => ref.current?.click()}
      onKeyDown={(event) => (event.key === "Enter" || event.key === " ") && ref.current?.click()}
      onDragOver={(event: DragEvent) => event.preventDefault()}
      onDrop={(event: DragEvent) => { event.preventDefault(); handle(event.dataTransfer.files); }}
      role="button"
      tabIndex={0}
    >
      <div><span className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-blue-100 text-blue-600">{icon}</span><p className="font-semibold text-slate-800">{label}</p><p className="mt-1 text-sm text-slate-500">{hint}</p></div>
      <input ref={ref} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,image/*" multiple={multiple} capture={capture ? "environment" : undefined} onChange={(event: ChangeEvent<HTMLInputElement>) => handle(event.target.files)} />
    </div>
  );
}

function FileChip({ file, remove }: { file: File; remove: () => void }) {
  return (
    <div className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3">
      <div className="min-w-0"><p className="truncate text-sm font-semibold">{file.name}</p><p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p></div>
      <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" onClick={(event) => { event.stopPropagation(); remove(); }} aria-label={`Remove ${file.name}`}><X size={18} /></button>
    </div>
  );
}
