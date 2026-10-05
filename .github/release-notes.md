## 📥 Download

**[{{FILE}}](https://github.com/Gioxfight/A2Timers/releases/download/{{TAG}}/{{FILE}})** — Windows 10/11, no admin rights needed.

## 🔒 È sicuro? / Is it safe?

- 🇮🇹 Il tool **non legge il gioco** (né memoria, né file, né traffico di rete): calcola gli orari dall'orologio del PC. L'unica connessione è a `api.github.com` per controllare gli aggiornamenti (disattivabile). Il codice è tutto pubblico in questo repository.
- 🇬🇧 The tool **never touches the game** (no memory, files or network capture): it only does clock math. Its only connection is to `api.github.com` to check for updates (can be turned off). All source code is public in this repository.

**Questo file è stato costruito da GitHub Actions direttamente da questo codice sorgente, non su un PC privato. / This file was built by GitHub Actions straight from this source code, not on a private PC.**

### Verifica il file / Verify the file

**SHA-256:** `{{HASH}}`

1. PowerShell — the result must match the hash above:
   ```powershell
   Get-FileHash .\{{FILE}}
   ```
2. Build provenance (proves it was built by this repository's workflow at commit `{{SHA}}`), with [GitHub CLI](https://cli.github.com/):
   ```powershell
   gh attestation verify .\{{FILE}} --repo Gioxfight/A2Timers
   ```

Windows SmartScreen may warn because the installer is not code-signed yet: **More info → Run anyway** / **Ulteriori informazioni → Esegui comunque**.
