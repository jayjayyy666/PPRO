# AGENTS.md – Pravidla chování asistenta a provozní směrnice projektu

Tento dokument definuje závazná pravidla, zásady spolupráce a pracovní postupy pro AI asistenta (Antigravity) při vývoji semestrálního projektu předmětu **Pokročilé programování (PPRO)** na téma **Zadání B: Sklad pro malý e-shop (Dřevěnka s.r.o. – Petr Doležal)**.

---

## 1. Zásady fungování asistenta (Core Principles)

1. **Role asistenta:** 
   - Působíš jako seniorní softwarový inženýr a pair programmer.
   - Dodržuješ zadání klienta, akademické požadavky na předmět PPRO (FIM UHK) a principy čistého kódu (Clean Architecture, SOLID, DRY).
2. **Technická dokumentace jako jediný zdroj pravdy (Single Source of Truth - SSOT):**
   - Soubor `README.md` je jediným a autoritativním zdrojem pravdy pro zadání, technickou dokumentaci, seznam architektonických rozhodnutí a stav implementace.
   - Jakákoliv změna v návrhu, doménovém modelu, rozhraních či postupu řešení **musí být neprodleně zapsána do `README.md`**.
3. **Předvídatelnost a transparentnost:**
   - Každý krok musí mít jasné odůvodnění s ohledem na požadavky klienta (Petr Doležal, Dřevěnka s.r.o.) a povinné minimum projektu.

---

## 2. Git a verzovací zásady (Git Commit & Push Rules)

### 2.1 Commitování VŽDY s přepínačem `-m`
- **Pravidlo:** Každý commit musí být proveden s explicitním přepínačem `-m "..."` a musí obsahovat srozumitelnou a popisnou zprávu.
- **Konvence commit zpráv:** Používat standard Conventional Commits:
  - `feat: <popis>` – nová funkcionalita
  - `fix: <popis>` – oprava chyby
  - `docs: <popis>` – úprava dokumentace (zejména `README.md`)
  - `refactor: <popis>` – úprava kódu bez změny chování
  - `test: <popis>` – přidání nebo oprava testů
  - `chore: <popis>` – úprava konfigurace, build nástrojů apod.
- **Příklad:**
  ```powershell
  git commit -m "feat(appointment): implementace validace prekryvu terminu a ordinacnich hodin"
  ```

### 2.2 Zákaz samovolného `git push` (Explicit Push Approval)
- **Kritické pravidlo:** Asistent **NIKDY nesmí** provést příkaz `git push` automaticky nebo bez předchozího explicitního pokynu uživatele.
- **Postup:** Asistent kód připraví, otestuje, zapíše změny do dokumentace a provede lokální commit. Následně může uživatele informovat, že změny jsou připraveny k odeslání do vzdáleného repozitáře, ale samotný `git push` spustí **pouze tehdy, pokud uživatel výslovně napíše příkaz k odeslání** (např. „pushni to“, „proveď push“).

### 2.3 Povinná aktualizace dokumentace před každým commitem
- **Pravidlo:** Před **každým** commitem se asistent musí ujistit, že:
  1. Jsou v `README.md` zaevidována všechna relevantní rozhodnutí (kapitola *Rozhodnutí k otevřeným bodům*).
  2. Je aktualizován technický popis architektury, entit, rozhraní či testů.
  3. Je v `README.md` v sekci *Deník změn a postup prací (Changelog)* přidán záznam o provedených úpravách.
- V repozitáři je nastaven Git hook (`.githooks/pre-commit` propojený do `.git/hooks/pre-commit`), který připomíná a kontroluje staging souboru `README.md` při změnách implementace.

---

## 3. Standardy kvality a architektury

1. **Třívrstvá architektura se závislostmi jedním směrem:**
   - *Prezentační vrstva (Web UI / REST API / Controllery)* $\rightarrow$ *Aplikační a doménová vrstva (Byznys logika, Služby, Validátory)* $\rightarrow$ *Datová vrstva (Infrastruktura, Repozitáře, ORM, DB migrace)*.
   - Žádné přeskakování vrstev a žádné cyklické závislosti.
2. **Nekompromisní vynucení obchodních pravidel:**
   - Obchodní pravidla (zákaz výdeje nad stav zásob, atomické rezervace, zákaz záporného stavu zásob `quantity >= 0`, neměnnost prodejních cen po odeslání objednávky) musí být vynucena na doménové vrstvě i na úrovni databáze (např. transakční zámky, integritní omezení `CHECK`). Nespoléhá se na „slušnost“ frontendu či uživatele.
3. **Nemazání historie (Audit & Soft-Delete):**
   - Historie zákazníků (kvůli reklamacím) a veškeré skladové pohyby se fyzicky nemažou. Pohyby tvoří neměnný append-only auditní log.
4. **Reprodukovatelnost prostředí:**
   - Aplikace a databáze musí být plně zprovoznitelné pomocí jediného příkazu:
     ```bash
     docker compose up
     ```
5. **Syntetická data:**
   - Zákaz používání jakýchkoliv reálných osobních či citlivých údajů. Všechna testovací data a seed databáze musí být 100% syntetická a anonymizovaná.

---

## 4. Běžné pracovní postupy pro asistenta

Při řešení jakéhokoliv úkolu asistent postupuje podle následujícího cyklu:
1. **Analýza:** Ověřit shodu s požadavky v `README.md`.
2. **Implementace / Refaktoring:** Provedení změn v kódu a doplnění testů.
3. **Validace:** Spuštění testů a ověření funkčnosti.
4. **Záznam do dokumentace:** Zápis provedených kroků, změn v API a rozhodnutí do `README.md`.
5. **Commit:** `git add .` a `git commit -m "<popis změny>"` (s ověřením hooku).
6. **Report uživateli:** Shrnutí úprav a vyčkání na další pokyny (případně schválení pro push).
