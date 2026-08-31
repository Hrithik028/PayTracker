# PayTracker

PayTracker is a private, local-first payslip and shift comparison application for Windows. It accepts a payslip plus timing screenshots, extracts what it can with local tools, and gives you an editable review step before anything becomes a confirmed record.

The application stores confirmed records in SQLite, compares screenshot hours with paid hours and line-item calculations, and exports verified data to a formatted Excel workbook. It does **not** upload documents or extracted information to a cloud service.

> PayTracker is a record-keeping and comparison tool. It is not legal, tax, payroll or financial advice, and a displayed difference does not establish that an underpayment occurred.

## Privacy model

- All project files and runtime data stay under `D:\Project\PayTracker`.
- Uploaded documents are processed locally with PyMuPDF, OpenCV, Pillow and Tesseract.
- SQLite is the only database.
- No cloud database, analytics, telemetry, external AI API or generative AI model is used.
- Original uploads are served only through ID-validated preview endpoints; `uploads` is not a public static directory.
- Raw OCR text is stored locally for troubleshooting but is not logged to the console or included in Excel exports.
- Upload retention is transactional: if the payslip has no usable financial data, or any selected timetable image has no complete extracted shift, all new copies are removed and no draft record is created.
- PayTracker keeps generated safe-name copies while a record is being reviewed. If **Retain generated upload copies** is disabled, those copies are removed after confirmation. Deleting a record also removes its generated copies; source files selected in Windows are never deleted.
- Safe generated filenames and content-based file validation prevent trusting user-supplied names or extensions.
- Laptop-only mode binds to `127.0.0.1`.
- LAN mode is opt-in and intended only for a trusted private Wi-Fi network.

LAN mode in this first local version has no user login. Anyone on the same network who knows the URL may be able to open PayTracker. Never use LAN mode on public Wi-Fi, and never configure router port forwarding for port 8000.

On desktop, use the panel button beside the PayTracker logo to minimize or expand the sidebar. The preference is stored only in the browser on that device.

## Technology stack

Frontend:

- React, TypeScript and Vite
- Tailwind CSS
- A small first-party browser-history router (no routing service or external state)
- Lucide icons
- Vitest

Backend:

- Python 3.12 and FastAPI
- Pydantic validation
- SQLAlchemy with SQLite
- Alembic migrations
- PyMuPDF for embedded PDF text and scanned-page rendering
- Tesseract through `pytesseract`
- Pillow and OpenCV for local image preprocessing
- `openpyxl` for Excel exports
- pytest

FastAPI OpenAPI documentation is available at `http://127.0.0.1:8000/api/docs` while the app is running.

## Required software

1. Windows 10 or 11.
2. [Python 3.12 for Windows](https://www.python.org/downloads/windows/). Enable **Add python.exe to PATH** during installation.
3. Node.js 20 or later with npm.
4. Tesseract OCR for automatic image and scanned-PDF extraction.

Manual entry, editing, reconciliation and Excel export work without Tesseract.

## Installing Tesseract

Install a Windows Tesseract distribution locally. A common installation path is:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

After installation, either add its directory to your Windows `PATH` or open **Settings** in PayTracker and enter the full executable path. Setup detects `tesseract.exe` on `PATH` and also checks the common path above.

Only the OCR executable is outside the PayTracker project. It runs locally; documents are not transmitted anywhere.

## Initial setup

Open PowerShell in `D:\Project\PayTracker` and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup-paytracker.ps1
```

The setup script:

1. Refuses to run if the project is not at `D:\Project\PayTracker`.
2. checks for Python 3.12, Node.js and npm;
3. creates `.venv` inside this project;
4. installs backend packages into that virtual environment;
5. installs frontend packages and builds the production frontend;
6. creates local data folders;
7. runs Alembic migrations against `data\paytracker.db`;
8. checks Tesseract;
9. creates fictional sample files under `samples`.

Package-manager caches and a separately installed Tesseract are normal system-level tooling; PayTracker application data remains inside this project.

## Starting PayTracker

Laptop-only access:

```powershell
cd D:\Project\PayTracker
.\start-paytracker.ps1
```

Open:

```text
http://127.0.0.1:8000
```

You can also double-click `start-paytracker.bat`.

### Phone access on private Wi-Fi

Connect your phone and laptop to the same trusted private Wi-Fi, then run:

```powershell
cd D:\Project\PayTracker
.\start-paytracker.ps1 -Lan
```

The script binds FastAPI to `0.0.0.0`, detects a private IPv4 address and prints a URL similar to:

```text
http://192.168.1.25:8000
```

Open the printed URL on the phone. Windows Firewall may ask for permission; allow **Private networks** only. The laptop must remain on, connected to Wi-Fi and running PayTracker. The script does not create public tunnels or expose the app to the public internet.

## Typical workflow

1. Select **New pay period**.
2. Add one payslip and zero or more timing screenshots.
3. Process the files locally.
   If extraction fails for any selected file, PayTracker removes every new copy from that submission and saves no database record.
4. Review every payslip field and line item. Low-confidence fields are highlighted.
5. Confirm the payslip review.
6. Review, add or delete daily shift rows. Every extracted IN/OUT punch pair remains visible and editable inside its day; pairs can also be added or removed. Date, break and category are editable, while rounded daily bounds, weekday and worked hours recalculate automatically. Break choices are No break, 1 hour or 2 hours. Clock-ins round forward and clock-outs round backward to 15-minute boundaries, matching the attendance application's displayed totals. Worked hours appear both as decimal hours and hours/minutes; finish times earlier than start times are treated as after midnight.
7. Review warnings and reconciliation differences.
   The daily table places each pay-category subtotal difference beside that category's last listed day, while clearly labelling it as a category total rather than attributing the difference to that individual date.
   The estimated-pay card multiplies screenshot hours by the matching payslip rate for each category and compares that estimate with the paid category amounts. It only shows a potentially-above or potentially-below direction when every worked category has a matching rate and paid amount; otherwise it reports an incomplete estimate. This is a comparison aid, not a legal finding of overpayment or underpayment.
8. Select **Confirm and save record**. Draft extraction is never counted in dashboard totals or exports.
9. Export a confirmed record from reconciliation/history, or export confirmed records through the API. The Timesheets worksheet includes both the shift date and weekday.

Edits to a confirmed record move it back to **Needs Review** and clear its confirmation time.

## Validation and discrepancy labels

PayTracker warns about:

- hours × rate differing from a line-item amount;
- gross pay differing from earnings line items;
- net pay differing from gross minus tax and deductions;
- missing or reversed pay-period dates;
- negative hours, rates or amounts;
- unusually large hourly rates that may be OCR decimal errors;
- duplicate payslips and screenshots;
- shifts outside the pay period;
- overlapping shifts;
- equal start and finish times;
- corrupted, unsupported or extension-spoofed files.

Values are not silently “fixed.” Money uses Python `Decimal`, and warnings remain review prompts. Material differences use the wording **Potential discrepancy—review required**.

## Local folders

| Path | Purpose |
| --- | --- |
| `data\paytracker.db` | Local SQLite database |
| `uploads\payslips` | Original payslips with generated filenames |
| `uploads\timing-screenshots` | Original timing images |
| `exports` | Timestamped Excel workbooks |
| `backups` | Timestamped local backups |
| `backend\.env` | Optional local configuration |
| `samples` | Fictional test documents only |

The database stores safe relative file paths, never arbitrary absolute upload paths.

These local-data folders are excluded by `.gitignore`. Do not force-add databases, uploads, exports, backups, `.env` files or OCR output to Git.

## Excel export

Every timestamped `.xlsx` export includes:

1. Summary
2. Payslips
3. Pay Items
4. Timesheets
5. Reconciliation
6. Monthly Summary

Sheets use frozen headers, filters, useful widths, AUD and date formats, decimal-hour formats and discrepancy highlighting. The summary includes formulas and the workbook metadata includes the export time. Raw OCR text and original documents are excluded.

Exports are written to `D:\Project\PayTracker\exports` and are also returned from an ID-validated download endpoint. A new timestamped file is created for each export.

## Backups and restore

Create a backup:

```powershell
cd D:\Project\PayTracker
.\backup-paytracker.ps1
```

The script copies the SQLite database, uploads, existing Excel exports and local configuration into:

```text
D:\Project\PayTracker\backups\paytracker-backup-YYYYMMDD-HHMMSS
```

It never deletes older backups.

To restore:

1. Stop PayTracker.
2. Create a fresh backup of the current state.
3. Open the desired timestamped backup.
4. Copy its `data`, `uploads` and `exports` folders back into `D:\Project\PayTracker`, deliberately replacing only the files you intend to restore.
5. Copy `configuration\.env` to `backend\.env` if needed.
6. Start PayTracker and check `/api/health`.

Restoring overwrites local state, so inspect the source and destination carefully before copying.

## Adding a payslip layout

The extraction design separates file/OCR processing from parsing:

- `backend\app\services\extraction.py` extracts local text.
- `backend\app\parsers\generic_payslip.py` contains conservative generic rules.
- `backend\app\parsers\generic_shifts.py` parses timing text separately.
- `backend\app\parsers\common.py` contains deterministic date, money, decimal and time helpers.
- `backend\app\parsers\registry.py` selects layout-specific parsers before the generic fallback.

To add a layout:

1. Add a new parser module under `backend\app\parsers`.
2. Give it a stable parser name and a `parse(text)` method that returns the same structured fields and per-field confidence values.
3. Add a narrow detection rule based on non-sensitive layout markers.
4. Register it before the generic fallback.
5. Add a synthetic fixture and parser tests.
6. Keep unknown fields blank rather than guessing.

Do not log source text and do not add a cloud or generative-AI dependency.

## Known OCR limitations

- OCR quality depends on screenshot resolution, crop, contrast, compression and font.
- Tesseract can confuse `0/O`, `1/I`, punctuation and decimal points.
- Tables with unusual column ordering may fall back to manual rows.
- Handwriting is unreliable.
- The generic parser intentionally prefers blank fields over confident-looking guesses.
- Some text PDFs use custom encodings and may still need OCR.
- Automatic rotation is best effort.

Always compare the review form with the original preview before confirmation.

## Running tests

Backend:

```powershell
cd D:\Project\PayTracker\backend
..\.venv\Scripts\python.exe -m pytest
```

Frontend:

```powershell
cd D:\Project\PayTracker\frontend
npm.cmd test
npm.cmd run build
```

The test suite covers Decimal money behavior, breaks and overnight shifts, date/currency parsing, duplicate hashes, file contents, path traversal, Excel output, payslip arithmetic warnings and API creation/edit/confirmation.

## Troubleshooting

### Python 3.12 was not found

Install Python 3.12, enable the PATH option, close and reopen PowerShell, then verify:

```powershell
python --version
```

### Tesseract was not found

Manual entry still works. Install Tesseract and enter its full `tesseract.exe` path in Settings. Restart PayTracker after changing it.

### PowerShell blocks a script

Use a process-scoped policy that disappears when the window closes:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### Port 8000 is already in use

Stop the other process using port 8000, or close an older PayTracker window. The phone URL and production frontend expect port 8000.

### Phone cannot connect

- Confirm both devices are on the same Wi-Fi and mobile data isolation is not active.
- Use `-Lan`, not laptop-only mode.
- Keep the PowerShell window open.
- Allow Python on **Private networks** in Windows Firewall.
- Some guest Wi-Fi networks block communication between devices.

### Frontend build is missing

Rerun:

```powershell
.\setup-paytracker.ps1
```

### Database migration fails

Stop PayTracker, create a backup, then run:

```powershell
cd D:\Project\PayTracker\backend
..\.venv\Scripts\python.exe -m alembic upgrade head
```

## Completely removing local data

Stop PayTracker first. The private runtime data is contained in:

- `D:\Project\PayTracker\data`
- `D:\Project\PayTracker\uploads`
- `D:\Project\PayTracker\exports`
- `D:\Project\PayTracker\backups`
- `D:\Project\PayTracker\backend\.env`

Deleting those paths permanently removes the local database, source documents, exports, backups and configuration. Review the paths carefully and create an offline backup first if anything may be needed later. Removing the whole `D:\Project\PayTracker` directory also removes the application code and virtual environment.

## API highlights

- `GET /api/health`
- `GET|PUT /api/settings`
- `GET|POST /api/pay-periods`
- `GET|PUT|DELETE /api/pay-periods/{id}`
- `POST /api/pay-periods/{id}/confirm`
- `POST /api/process`
- `GET /api/documents/{type}/{id}`
- `GET /api/dashboard`
- `POST /api/exports`
- `GET /api/exports/{id}/download`

Use the interactive OpenAPI page at `/api/docs` for current request and response schemas.
