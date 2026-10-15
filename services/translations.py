"""Every word the interface says, in both languages.

One dictionary, keyed by a name rather than by the
English text, so a change to the English does not silently
orphan the Polish. Both languages sit side by side in the
same entry: a missing translation is visible while
reading, and `tests.translation_test` refuses to pass
while one exists.

The agents are deliberately not translated. Their answers
are parsed -- the review markers, and eighteen regular
expressions that strip the structural claims the model is
not allowed to make. Those match English. An architect
answering in Polish would slip every one of them, and the
grounding built over two sprints would stop working
without saying so.
"""

LANGUAGES = {
    "pl": "Polski",
    "en": "English",
}

DEFAULT_LANGUAGE = "pl"

MESSAGES: dict[str, dict[str, str]] = {
    # ---------------------------------------------- app
    "app.describe_task": {
        "pl": "Opisz zadanie dla AI",
        "en": "Describe the task for the AI",
    },
    "app.generate": {
        "pl": "Generuj kod",
        "en": "Generate code",
    },
    "app.language": {
        "pl": "Język",
        "en": "Language",
    },
    "app.working": {
        "pl": "🤖 Developer → Architekt → QA ...",
        "en": "🤖 Developer → Architect → QA ...",
    },
    "app.select_repository_first": {
        "pl": (
            "Dodaj i wybierz repozytorium, zanim "
            "utworzysz zadanie."
        ),
        "en": (
            "Add and select a repository before "
            "creating a task."
        ),
    },
    # --------------------------------------- repositories
    "repo.heading": {
        "pl": "📦 Repozytoria",
        "en": "📦 Repositories",
    },
    "repo.add": {
        "pl": "➕ Dodaj repozytorium",
        "en": "➕ Add repository",
    },
    "repo.remove": {"pl": "🗑 Usuń", "en": "🗑 Remove"},
    "repo.name": {"pl": "Nazwa", "en": "Name"},
    "repo.path": {"pl": "Ścieżka", "en": "Path"},
    "repo.active": {
        "pl": "Aktywne repozytorium",
        "en": "Active repository",
    },
    "repo.none_yet": {
        "pl": "Brak repozytoriów. Dodaj jedno poniżej.",
        "en": "No repositories yet. Add one below.",
    },
    "repo.name_and_path_required": {
        "pl": "Nazwa i ścieżka są wymagane.",
        "en": "Name and path are both required.",
    },
    "repo.already_registered": {
        "pl": "Ten katalog jest już zarejestrowany.",
        "en": "That folder is already registered.",
    },
    "repo.path_missing": {
        "pl": (
            "Nie znaleziono ścieżki na tej maszynie. "
            "Generowanie plików wymaga istniejącego "
            "katalogu."
        ),
        "en": (
            "Path not found on this machine. File "
            "generation will need a real folder."
        ),
    },
    # ------------------------------------------- context
    "context.typescript": {
        "pl": "TypeScript",
        "en": "TypeScript",
    },
    "context.tests_runnable": {
        "pl": "Testy uruchamialne",
        "en": "Tests runnable",
    },
    "context.package_json": {
        "pl": "package.json",
        "en": "package.json",
    },
    "context.git": {"pl": "Git", "en": "Git"},
    "context.vitest_not_installed": {
        "pl": (
            "Vitest jest skonfigurowany, ale "
            "niezainstalowany, więc bramka testów nie "
            "może działać."
        ),
        "en": (
            "Vitest is configured but not installed, so "
            "the test gate cannot run."
        ),
    },
    "context.gate_cannot_run": {
        "pl": (
            "Bramka testów nie może tu działać, więc "
            "każde zadanie w tym planie zgłosi "
            "UNAVAILABLE zamiast przejść albo polec. "
        ),
        "en": (
            "The test gate cannot run here, so every "
            "task in this plan will report UNAVAILABLE "
            "rather than passing or failing. "
        ),
    },
    "context.dependencies_missing": {
        "pl": "Zależności nie są zainstalowane.",
        "en": "Dependencies are not installed.",
    },
    "context.not_vitest": {
        "pl": (
            "Ten projekt nie jest ustawiony pod Vitest, "
            "a to jedyny runner, który ta platforma "
            "obsługuje."
        ),
        "en": (
            "This project is not set up for Vitest, "
            "which is the only runner this platform "
            "drives."
        ),
    },
    # ------------------------------------------- install
    "install.run": {
        "pl": "📦 Uruchom npm install",
        "en": "📦 Run npm install",
    },
    "install.spinner": {
        "pl": "📦 npm install ...",
        "en": "📦 npm install ...",
    },
    "install.output": {
        "pl": "📦 Wyjście npm",
        "en": "📦 npm output",
    },
    "install.warning": {
        "pl": (
            "📦 To pobiera pakiety i uruchamia ich "
            "skrypty instalacyjne. Nic innego w tej "
            "platformie tego nie robi."
        ),
        "en": (
            "📦 This downloads packages and runs their "
            "install scripts. Nothing else in this "
            "platform does that."
        ),
    },
    "install.switched_off": {
        "pl": (
            "📦 `npm install` jest wyłączony. Ustaw "
            "`ENABLE_PACKAGE_INSTALLATION = True` w "
            "config/settings.py, aby włączyć przycisk."
        ),
        "en": (
            "📦 `npm install` is switched off. Set "
            "`ENABLE_PACKAGE_INSTALLATION = True` in "
            "config/settings.py to enable the button."
        ),
    },
    # ---------------------------------------- requirements
    "requirement.heading": {
        "pl": "🧠 Wymagania",
        "en": "🧠 Requirements",
    },
    "requirement.one": {
        "pl": "🧠 Wymaganie",
        "en": "🧠 Requirement",
    },
    "requirement.new": {
        "pl": "➕ Nowe wymaganie",
        "en": "➕ New requirement",
    },
    "requirement.title": {"pl": "Tytuł", "en": "Title"},
    "requirement.description": {
        "pl": "Opis wymagania",
        "en": "Requirements description",
    },
    "requirement.description_help": {
        "pl": (
            "Historyjki użytkownika, wymagania "
            "funkcjonalne i niefunkcjonalne, "
            "ograniczenia architektury, kryteria "
            "akceptacji."
        ),
        "en": (
            "User stories, functional and "
            "non-functional requirements, architecture "
            "constraints, acceptance criteria."
        ),
    },
    "requirement.save": {"pl": "💾 Zapisz", "en": "💾 Save"},
    "requirement.delete": {
        "pl": "🗑 Usuń",
        "en": "🗑 Delete",
    },
    "requirement.none_yet": {
        "pl": "Brak wymagań.",
        "en": "No requirements yet.",
    },
    "requirement.status_new": {
        "pl": "Status: NOWE",
        "en": "Status: NEW",
    },
    "requirement.generate_plan": {
        "pl": "🧠 Generuj plan",
        "en": "🧠 Generate plan",
    },
    # ------------------------------------------- issues
    "issue.heading": {
        "pl": "📥 Zgłoszenia GitHub",
        "en": "📥 GitHub Issues",
    },
    "issue.load": {
        "pl": "🔄 Wczytaj otwarte zgłoszenia",
        "en": "🔄 Load open issues",
    },
    "issue.needs_github_remote": {
        "pl": (
            "Wybierz repozytorium git ze zdalnym "
            "adresem GitHub."
        ),
        "en": (
            "Select a git repository with a GitHub "
            "remote."
        ),
    },
    # --------------------------------------------- plans
    "plan.heading": {"pl": "📋 Plany", "en": "📋 Plans"},
    "plan.open_task": {
        "pl": "🔍 Otwórz zadanie",
        "en": "🔍 Open the task",
    },
    "plan.review_waiting": {
        "pl": "⏳ Czeka na Twoją decyzję: otwórz, przejrzyj, zaakceptuj albo odrzuć.",
        "en": "⏳ Waiting for your decision: open it, review it, accept or reject.",
    },
    "plan.review_committed": {
        "pl": "✅ Zaakceptowane i zacommitowane ({hash}).",
        "en": "✅ Accepted and committed ({hash}).",
    },
    "plan.review_rejected": {
        "pl": "❌ Odrzucone w review.",
        "en": "❌ Rejected in review.",
    },
    "plan.rejected_in_review": {
        "pl": "Odrzucone w review — pliki cofnięte; uruchom ponownie.",
        "en": "Rejected in review — files undone; run it again.",
    },
    "task.rolled_back": {
        "pl": (
            "Odrzucono. Usunięto plików: {removed}, "
            "przywrócono z gita: {restored}."
        ),
        "en": (
            "Rejected. Files removed: {removed}, restored "
            "from git: {restored}."
        ),
    },
    "task.rollback_kept": {
        "pl": (
            "Zostawiono bez zmian (istniały wcześniej, a git "
            "ich nie zna): {names}"
        ),
        "en": (
            "Left as they are (they existed before and git "
            "does not know them): {names}"
        ),
    },
    "task.rollback_failed": {
        "pl": "Nie odrzucono — pliki nie zostały cofnięte: {reason}",
        "en": "Not rejected — the files could not be undone: {reason}",
    },
    "task.later_on_branch": {
        "pl": (
            "Uwaga: {count} późniejsze zadanie(a) na tej "
            "gałęzi powstały na odrzuconym kodzie — odrzuć je "
            "też i uruchom ponownie."
        ),
        "en": (
            "Note: {count} later task(s) on this branch were "
            "built on the rejected code — reject them too and "
            "run them again."
        ),
    },
    "env.heading": {
        "pl": "**Krok 0 · Środowisko** — do zrobienia przed pierwszym zadaniem",
        "en": "**Step 0 · Environment** — to do before the first task",
    },
    "env.heading_ready": {
        "pl": "**Krok 0 · Środowisko** ✅ gotowe",
        "en": "**Step 0 · Environment** ✅ ready",
    },
    "env.no_git": {
        "pl": (
            "Ten folder nie jest repozytorium git. Uruchom "
            "w nim `git init` — bez tego żadnego zadania nie "
            "da się zacommitować."
        ),
        "en": (
            "This folder is not a git repository. Run "
            "`git init` in it — without that no task can be "
            "committed."
        ),
    },
    "env.scaffolding_missing": {
        "pl": "⬜ Szkielet projektu: brakuje {names}",
        "en": "⬜ Project scaffolding: {names} missing",
    },
    "env.scaffolding_ok": {
        "pl": "✅ Szkielet projektu jest na miejscu",
        "en": "✅ Project scaffolding is in place",
    },
    "env.create_scaffolding": {
        "pl": "🧱 Utwórz szkielet z szablonów",
        "en": "🧱 Write the scaffolding from templates",
    },
    "env.scaffolding_created": {
        "pl": "Utworzono z szablonów: {names}",
        "en": "Written from templates: {names}",
    },
    "env.dependencies_missing": {
        "pl": (
            "⬜ Zależności: TypeScript i Vitest nie są "
            "zainstalowane, więc kodu nie da się "
            "skompilować ani przetestować"
        ),
        "en": (
            "⬜ Dependencies: TypeScript and Vitest are not "
            "installed, so the code can be neither compiled "
            "nor tested"
        ),
    },
    "env.dependencies_ok": {
        "pl": "✅ Zależności są zainstalowane",
        "en": "✅ Dependencies are installed",
    },
    "env.uncommitted": {
        "pl": (
            "⬜ Git: szkielet nie jest zacommitowany "
            "({names}), więc nie trafiłby do gałęzi zadań"
        ),
        "en": (
            "⬜ Git: the scaffolding is not committed "
            "({names}), so task branches would not have it"
        ),
    },
    "env.commit_scaffolding": {
        "pl": "📌 Zacommituj szkielet na {branch}",
        "en": "📌 Commit the scaffolding to {branch}",
    },
    "env.committed": {
        "pl": "Szkielet zacommitowany ({hash}).",
        "en": "Scaffolding committed ({hash}).",
    },
    "env.commit_failed": {
        "pl": "Nie udało się zacommitować szkieletu: {reason}",
        "en": "Could not commit the scaffolding: {reason}",
    },
    "env.committed_ok": {
        "pl": "✅ Szkielet jest w gicie",
        "en": "✅ The scaffolding is in git",
    },
    "env.skip": {
        "pl": (
            "Uruchamiaj zadania mimo to — kod nie zostanie "
            "skompilowany ani przetestowany"
        ),
        "en": (
            "Run tasks anyway — the code will be neither "
            "compiled nor tested"
        ),
    },
    "env.runs_blocked": {
        "pl": (
            "Zadania czekają na Krok 0. Dokończ "
            "środowisko albo zaznacz, że chcesz je "
            "uruchomić mimo to."
        ),
        "en": (
            "Tasks are waiting for Step 0. Finish the "
            "environment, or tick that you want to run "
            "them anyway."
        ),
    },
    "plan.usage": {
        "pl": "💰 Planowanie: {usage}",
        "en": "💰 Planning: {usage}",
    },
    "plan.planned_tasks": {
        "pl": "📋 Zaplanowane zadania",
        "en": "📋 Planned Tasks",
    },
    "plan.none_yet": {
        "pl": "Brak planów.",
        "en": "No plans yet.",
    },
    "plan.no_tasks": {
        "pl": "Brak zadań.",
        "en": "No tasks.",
    },
    "plan.dependency_graph": {
        "pl": "Graf zależności",
        "en": "Dependency graph",
    },
    "plan.planner_spinner": {
        "pl": "🧠 Planer ...",
        "en": "🧠 Planner ...",
    },
    "plan.close": {
        "pl": "🗑 Zamknij plan",
        "en": "🗑 Close plan",
    },
    "cost.plan": {
        "pl": "💰 Plan kosztował dotąd ${spent} (planowanie, wszystkie próby i rewizje){limit}",
        "en": "💰 The plan has cost ${spent} so far (planning, every attempt and revision){limit}",
    },
    "cost.of_limit": {
        "pl": " · limit ${limit}",
        "en": " · limit ${limit}",
    },
    "cost.over_limit": {
        "pl": "Plan osiągnął limit kosztów (${limit}, PLAN_COST_LIMIT). Nowe zadania nie startują; podnieś limit w config/settings.py, jeśli chcesz kontynuować.",
        "en": "The plan has reached its cost limit (${limit}, PLAN_COST_LIMIT). No new task starts; raise the limit in config/settings.py to carry on.",
    },
    "cost.history": {
        "pl": "📊 Historia kosztów",
        "en": "📊 Cost history",
    },
    "cost.history_heading": {
        "pl": "📊 Koszty: ostatnie 30 dni",
        "en": "📊 Costs: the last 30 days",
    },
    "cost.history_total": {
        "pl": "Razem w tych 30 dniach: ${spent}",
        "en": "In all over these 30 days: ${spent}",
    },
    "cost.per_plan": {
        "pl": "Plany, od najdroższego",
        "en": "Plans, costliest first",
    },
    "cost.column_day": {
        "pl": "Dzień",
        "en": "Day",
    },
    "cost.column_usd": {
        "pl": "USD",
        "en": "USD",
    },
    "cost.column_plan": {
        "pl": "Plan",
        "en": "Plan",
    },
    "cost.close": {
        "pl": "Zamknij historię kosztów",
        "en": "Close the cost history",
    },
    "cost.month": {
        "pl": "💰 Ten miesiąc: ${spent}",
        "en": "💰 This month: ${spent}",
    },
    "run.in_progress": {
        "pl": "⚙️ Przebieg w tle ({status}): zadanie {task} · gotowe w tym przebiegu: {done} · od {since}",
        "en": "⚙️ Running in the background ({status}): task {task} · done in this run: {done} · since {since}",
    },
    "run.task_in_progress": {
        "pl": "⚙️ W toku, w tle. Możesz zamknąć kartę; przebieg trwa dalej.",
        "en": "⚙️ In progress, in the background. You can close the tab; the run carries on.",
    },
    "run.ended": {
        "pl": "Ostatni przebieg: {status}. {message}",
        "en": "Last run: {status}. {message}",
    },
    "run.could_not_start": {
        "pl": "Nie uruchomiono: {reason}",
        "en": "Not started: {reason}",
    },
    "plan.stop_after_task": {
        "pl": "⏹ Zatrzymaj po tym zadaniu",
        "en": "⏹ Stop after this task",
    },
    "plan.run_task": {
        "pl": "▶️ Uruchom to zadanie",
        "en": "▶️ Run this task",
    },
    "plan.run_again": {
        "pl": "🔁 Uruchom ponownie",
        "en": "🔁 Run again",
    },
    "plan.done": {"pl": "Wykonane.", "en": "Done."},
    "plan.marked_running": {
        "pl": (
            "Oznaczone jako uruchomione. Jeśli "
            "aplikacja została przerwana, uruchom "
            "ponownie."
        ),
        "en": (
            "Marked as running. If the application was "
            "interrupted, run it again."
        ),
    },
    "plan.log": {
        "pl": "🪵 Dziennik wykonania ({count})",
        "en": "🪵 Execution log ({count})",
    },
    "plan.now_running": {
        "pl": (
            "⏳ **Wykonywane teraz — zadanie {id}:** "
            "{title}"
        ),
        "en": "⏳ **Running now — task {id}:** {title}",
    },
    "plan.depends_on": {
        "pl": "Zależy od: {ids}",
        "en": "Depends on: {ids}",
    },
    "plan.waiting_for": {
        "pl": "Czeka na: {ids}",
        "en": "Waiting for: {ids}",
    },
    "plan.failed": {
        "pl": "Nie powiodło się: {reason}",
        "en": "Failed: {reason}",
    },
    "plan.run_all": {
        "pl": "⏩ Uruchom cały plan ({count})",
        "en": "⏩ Run the whole plan ({count})",
    },
    "plan.progress": {
        "pl": "{done} / {total} ukończonych ({percent}%)",
        "en": "{done} / {total} completed ({percent}%)",
    },
    "plan.step": {"pl": "**Krok {n}**", "en": "**Step {n}**"},
    "plan.task_failed": {
        "pl": "Zadanie {id} nie powiodło się: {reason}",
        "en": "Task {id} failed: {reason}",
    },
    "plan.stopped_before": {
        "pl": "Zatrzymano przed zadaniem {id}: czeka na {ids}",
        "en": "Stopped before task {id}: waiting for {ids}",
    },
    "plan.stopped_at": {
        "pl": "Zatrzymano na zadaniu {id}: {reason}",
        "en": "Stopped at task {id}: {reason}",
    },
    "plan.problems": {
        "pl": (
            "Planer zgłosił {count} problem(ów) z "
            "podziałem, który zaproponował:"
        ),
        "en": (
            "The planner reported {count} problem(s) "
            "with the breakdown it proposed:"
        ),
    },
    "context.scaffolding_off": {
        "pl": "Brakuje, a AUTO_BOOTSTRAP jest wyłączony: {names}",
        "en": "Missing, and AUTO_BOOTSTRAP is off: {names}",
    },
    "plan.scaffolding_created": {
        "pl": (
            "Tworzone automatycznie przed pierwszym "
            "zadaniem: {names}"
        ),
        "en": (
            "Created automatically before the first "
            "task runs: {names}"
        ),
    },
    # --------------------------------------- log events
    "log.started": {"pl": "Rozpoczęto", "en": "Started"},
    "log.completed": {"pl": "Ukończono", "en": "Completed"},
    "log.failed": {
        "pl": "Nie powiodło się",
        "en": "Failed",
    },
    "log.entry": {
        "pl": "`{at}` {icon} {verb} — zadanie {id}: {title}",
        "en": "`{at}` {icon} {verb} — task {id}: {title}",
    },
    "log.running": {
        "pl": "Uruchomiono",
        "en": "Running",
    },
    "task.status_now": {
        "pl": "Status: {status}",
        "en": "Status: {status}",
    },
    "repo.current": {
        "pl": "Repozytorium: {name}",
        "en": "Repository: {name}",
    },
    "requirement.imported_from": {
        "pl": "Zaimportowane ze zgłoszenia {label}",
        "en": "Imported from issue {label}",
    },
    "plan.planner_failed": {
        "pl": "Planer zawiódł: {reason}",
        "en": "Planner failed: {reason}",
    },
    "app.folder_missing": {
        "pl": (
            "Katalog repozytorium nie istnieje, więc nie "
            "zapisano żadnych plików: {path}"
        ),
        "en": (
            "Repository folder does not exist, so no "
            "files could be written: {path}"
        ),
    },
    "app.workflow_failed": {
        "pl": "Przebieg zawiódł: {reason}",
        "en": "Workflow failed: {reason}",
    },
    "task.created": {
        "pl": "**Utworzono:** {when}",
        "en": "**Created:** {when}",
    },
    "task.status_line": {
        "pl": "**Status:** {status}",
        "en": "**Status:** {status}",
    },
    "task.repository_line": {
        "pl": "**Repozytorium:** {name}",
        "en": "**Repository:** {name}",
    },
    "task.description_line": {
        "pl": "**Opis:** {text}",
        "en": "**Description:** {text}",
    },
    "tests.failed_summary": {
        "pl": "🧪 Testy NIEZDANE — {summary}",
        "en": "🧪 Tests FAILED — {summary}",
    },
    "tests.passed_summary": {
        "pl": "🧪 Testy ZDANE — {summary}",
        "en": "🧪 Tests PASSED — {summary}",
    },
    "structural.count_see_review": {
        "pl": (
            "🧱 {count} ustaleń strukturalnych — zobacz "
            "Recenzję architektury."
        ),
        "en": (
            "🧱 {count} structural finding(s) — see "
            "Architecture Review."
        ),
    },
    "structural.count": {
        "pl": "🧱 {count} ustaleń strukturalnych",
        "en": "🧱 {count} structural finding(s)",
    },
    "repo.context_heading": {
        "pl": "📦 Kontekst repozytorium — {state}",
        "en": "📦 Repository context — {state}",
    },
    "repo.remove_anyway": {
        "pl": "Usuń mimo to ({count} powiązanych zadań)",
        "en": "Remove anyway ({count} task(s) linked)",
    },
    "context.other_framework": {
        "pl": (
            "Ten projekt używa {framework}. Bramka "
            "testów obsługuje tylko Vitest, więc "
            "wygenerowane testy nie zostaną uruchomione."
        ),
        "en": (
            "This project uses {framework}. The test "
            "gate drives Vitest only, so generated "
            "tests will not be run."
        ),
    },
    "history.iteration": {
        "pl": "Runda {n}",
        "en": "Iteration {n}",
    },
    "history.score": {
        "pl": "Ocena: {score}",
        "en": "Score: {score}",
    },
    "history.recommendation": {
        "pl": "Rekomendacja: {value}",
        "en": "Recommendation: {value}",
    },
    "tests.duration": {
        "pl": "Czas",
        "en": "Duration",
    },
    "tests.executed_at": {
        "pl": "Wykonano: {when}",
        "en": "Executed: {when}",
    },
    "files.written_to": {
        "pl": "Zapisano do {path}",
        "en": "Written to {path}",
    },
    "diff.already_matching": {
        "pl": "{count} plik(ów) już zgadza się z repozytorium.",
        "en": "{count} file(s) already match the repository.",
    },
    "diff.already_committed": {
        "pl": "Te zmiany są już zacommitowane jako {hash}.",
        "en": "These changes are already committed as {hash}.",
    },
    "git.committed_to": {
        "pl": "Zacommitowano do `{branch}`",
        "en": "Committed to `{branch}`",
    },
    "git.created_at": {
        "pl": "Utworzono: {when}",
        "en": "Created: {when}",
    },
    "git.not_a_repository": {
        "pl": (
            "Katalog nie jest repozytorium git, więc nic "
            "nie da się zacommitować: {path}"
        ),
        "en": (
            "The repository folder is not a git "
            "repository, so nothing can be committed: "
            "{path}"
        ),
    },
    "git.push_succeeded": {
        "pl": "Wypchnięto: {where}",
        "en": "Push status: SUCCESS — `{where}`",
    },
    "git.push_failed": {
        "pl": "Wypchnięcie nie powiodło się: {reason}",
        "en": "Push status: FAILED — {reason}",
    },
    "git.pushed": {
        "pl": "Wypchnięto: {where}",
        "en": "Pushed: {where}",
    },
    "git.branch_line": {
        "pl": "**Gałąź:** `{branch}`",
        "en": "**Branch:** `{branch}`",
    },
    "git.remote_line": {
        "pl": "**Zdalne:** `{remote}`",
        "en": "**Remote:** `{remote}`",
    },
    "git.files_line": {
        "pl": "**Pliki:** {count}",
        "en": "**Files:** {count}",
    },
    "pr.repository_line": {
        "pl": "**Repozytorium:** `{owner}/{repo}`",
        "en": "**Repository:** `{owner}/{repo}`",
    },
    "pr.title_line": {
        "pl": "**Tytuł:** {title}",
        "en": "**Title:** {title}",
    },
    "pr.failed": {
        "pl": "Pull request nie powiódł się: {reason}",
        "en": "Pull request failed: {reason}",
    },
    "pr.state": {"pl": "Stan", "en": "State"},
    "context.summary_line": {
        "pl": (
            "{files} plik(ów) źródłowych · framework "
            "testów: {framework}{folders}"
        ),
        "en": (
            "{files} source file(s) · test framework: "
            "{framework}{folders}"
        ),
    },
    "context.folders_suffix": {
        "pl": " · katalogi: {names}",
        "en": " · folders: {names}",
    },
    "context.framework_none": {
        "pl": "brak",
        "en": "none",
    },
    "context.state_line": {
        "pl": "📦 {state} · {scaffolding}",
        "en": "📦 {state} · {scaffolding}",
    },
    "context.scaffolding_present": {
        "pl": "rusztowanie: {names}",
        "en": "scaffolding: {names}",
    },
    "context.scaffolding_missing": {
        "pl": "brakuje: {names}",
        "en": "missing: {names}",
    },
    "context.tests_state": {
        "pl": "🧪 testy: {state}",
        "en": "🧪 tests: {state}",
    },
    "context.tests_can_run": {
        "pl": "uruchamialne",
        "en": "runnable",
    },
    "context.tests_cannot_run": {
        "pl": "nie mogą działać",
        "en": "cannot run",
    },
    # -------------------------------------------- steps
    "steps.heading": {
        "pl": "🧭 Kroki ({count})",
        "en": "🧭 Steps ({count})",
    },
    "steps.none": {
        "pl": (
            "To zadanie powstało, zanim kroki były "
            "zapisywane."
        ),
        "en": (
            "This task ran before steps were recorded."
        ),
    },
    "step.bootstrap": {
        "pl": "Rusztowanie projektu",
        "en": "Project scaffolding",
    },
    "step.developer": {
        "pl": "Developer napisał kod",
        "en": "Developer wrote the code",
    },
    "step.architect": {
        "pl": "Recenzja architekta",
        "en": "Architect review",
    },
    "step.packages": {
        "pl": "Brakuje pakietów npm",
        "en": "npm packages are missing",
    },
    "step.recheck": {
        "pl": "Ponowne sprawdzenie tych samych plików",
        "en": "The same files checked again",
    },
    "packages.needed": {
        "pl": "📦 Ten kod importuje pakiety, których projekt nie ma: {names}. Kompilacja nie przejdzie, dopóki ich nie zainstalujesz. Sprawdź nazwy: wybrał je model.",
        "en": "📦 This code imports packages the project lacks: {names}. It cannot compile until they are installed. Check the names: a model chose them.",
    },
    "packages.install": {
        "pl": "📦 Zainstaluj {names} i sprawdź ponownie",
        "en": "📦 Install {names} and check again",
    },
    "packages.spinner": {
        "pl": "📦 Instaluję pakiety i sprawdzam kod ponownie ...",
        "en": "📦 Installing the packages and checking the code again ...",
    },
    "packages.done": {
        "pl": "Zainstalowano {names}. Nowa wersja zadania czeka na akceptację.",
        "en": "Installed {names}. The task's new version waits for approval.",
    },
    "packages.failed": {
        "pl": "Nie zainstalowano: {reason}",
        "en": "Not installed: {reason}",
    },
    "step.revision": {
        "pl": "Developer poprawił kod według uwag człowieka",
        "en": "Developer revised the code from a human's notes",
    },
    "requirement.create_issue": {
        "pl": "📤 Załóż issue na GitHubie",
        "en": "📤 Create a GitHub issue",
    },
    "requirement.issue_created": {
        "pl": "Założono {label}. Plan z tego wymagania dostanie gałąź issue.",
        "en": "Created {label}. A plan from this requirement gets the issue's branch.",
    },
    "requirement.issue_failed": {
        "pl": "Nie założono issue: {reason}",
        "en": "The issue was not created: {reason}",
    },
    "requirement.needs_remote": {
        "pl": "Issues wymagają repozytorium z remote na GitHubie i GITHUB_PAT.",
        "en": "Issues need a repository with a GitHub remote and GITHUB_PAT.",
    },
    "repo.pick": {
        "pl": "📁 Wybierz folder…",
        "en": "📁 Choose a folder…",
    },
    "repo.pick_none": {
        "pl": "Nie wybrano folderu (albo okno nie mogło się otworzyć). Wpisz ścieżkę.",
        "en": "No folder chosen (or the window could not open). Type the path instead.",
    },
    "repo.add_button": {
        "pl": "Dodaj",
        "en": "Add",
    },
    "repo.folder_missing": {
        "pl": "Ten folder nie istnieje: {path}",
        "en": "That folder does not exist: {path}",
    },
    "repo.not_git": {
        "pl": "Ten folder nie jest repozytorium git, więc nie da się w nim zrobić brancha ani uruchomić planu.",
        "en": "This folder is not a git repository, so no branch can be made and no plan can run in it.",
    },
    "repo.start_git": {
        "pl": "🌱 Zrób z niego repozytorium (git init)",
        "en": "🌱 Make it a repository (git init)",
    },
    "repo.git_started": {
        "pl": "Folder {path} jest teraz repozytorium git, na gałęzi main.",
        "en": "{path} is now a git repository, on main.",
    },
    "repo.git_start_failed": {
        "pl": "Nie udało się zrobić repozytorium: {reason}",
        "en": "Could not make a repository: {reason}",
    },
    "repo.inside": {
        "pl": "Ten folder leży wewnątrz repozytorium {root}. Dodaj całe repozytorium.",
        "en": "This folder is inside the repository {root}. Add the whole repository.",
    },
    "repo.use_root": {
        "pl": "Użyj {root}",
        "en": "Use {root}",
    },
    "repo.added": {
        "pl": "Dodano repozytorium {name}.",
        "en": "Added the repository {name}.",
    },
    "repo.new": {
        "pl": "🆕 Nowe repozytorium",
        "en": "🆕 New repository",
    },
    "repo.new_name": {
        "pl": "Nazwa (folder i repo na GitHubie)",
        "en": "Name (the folder, and the GitHub repository)",
    },
    "repo.new_parent": {
        "pl": "Folder nadrzędny",
        "en": "Parent folder",
    },
    "repo.new_description": {
        "pl": "Opis (opcjonalnie)",
        "en": "Description (optional)",
    },
    "repo.new_on_github": {
        "pl": "Załóż też na GitHubie i ustaw jako origin",
        "en": "Also create it on GitHub and set it as origin",
    },
    "repo.new_private": {
        "pl": "Prywatne",
        "en": "Private",
    },
    "repo.new_target": {
        "pl": "Powstanie: `{path}`",
        "en": "Will be created: `{path}`",
    },
    "repo.new_token_note": {
        "pl": (
            "Zakładanie repo na GitHubie wymaga tokena z uprawnieniem "
            "Administration: write. Użyty zostanie GITHUB_ADMIN_PAT, "
            "a jeśli go nie ma, GITHUB_PAT."
        ),
        "en": (
            "Creating a GitHub repository needs a token with "
            "Administration: write. GITHUB_ADMIN_PAT is used, or "
            "GITHUB_PAT when it is not set."
        ),
    },
    "repo.new_create": {
        "pl": "🆕 Utwórz repozytorium",
        "en": "🆕 Create the repository",
    },
    "repo.new_spinner": {
        "pl": "Tworzę repozytorium ...",
        "en": "Creating the repository ...",
    },
    "repo.new_created": {
        "pl": "Utworzono {name} w {path}.",
        "en": "Created {name} in {path}.",
    },
    "repo.new_created_github": {
        "pl": " Na GitHubie: {url}",
        "en": " On GitHub: {url}",
    },
    "repo.new_failed": {
        "pl": "Nie utworzono repozytorium: {reason}",
        "en": "The repository was not created: {reason}",
    },
    "split.button": {
        "pl": "✂️ Rozbij na issues",
        "en": "✂️ Split into issues",
    },
    "split.spinner": {
        "pl": "🤖 Planner dzieli wymaganie na historyjki ...",
        "en": "🤖 The planner is splitting the requirement into stories ...",
    },
    "split.failed": {
        "pl": "Nie udało się rozbić: {reason}",
        "en": "The split failed: {reason}",
    },
    "split.heading": {
        "pl": "✂️ Proponowany podział",
        "en": "✂️ Proposed split",
    },
    "split.caption": {
        "pl": (
            "Każda zaznaczona historyjka stanie się osobnym issue, "
            "a potem osobnym planem, gałęzią i PR. Popraw tytuły i "
            "treść przed założeniem."
        ),
        "en": (
            "Each ticked story becomes its own issue, and then its "
            "own plan, branch and pull request. Edit the titles and "
            "bodies before creating them."
        ),
    },
    "split.include": {
        "pl": "Załóż",
        "en": "Create",
    },
    "split.title": {
        "pl": "Tytuł",
        "en": "Title",
    },
    "split.body": {
        "pl": "Treść",
        "en": "Body",
    },
    "split.create": {
        "pl": "📤 Załóż {count} issue(s)",
        "en": "📤 Create {count} issue(s)",
    },
    "split.cancel": {
        "pl": "Anuluj",
        "en": "Cancel",
    },
    "split.created": {
        "pl": "Założono {count} issue(s): {labels}. Są na liście wymagań.",
        "en": "Created {count} issue(s): {labels}. They are in the requirements list.",
    },
    "split.partial": {
        "pl": "Założono {count} issue(s), potem błąd: {reason}",
        "en": "Created {count} issue(s), then it failed: {reason}",
    },
    "split.linked": {
        "pl": " Powiązane jako sub-issues #{parent}.",
        "en": " Linked as sub-issues of #{parent}.",
    },
    "split.not_linked": {
        "pl": " Nie powiązano jako sub-issues ({reason}); #{parent} dostało listę w komentarzu.",
        "en": " Not linked as sub-issues ({reason}); #{parent} got a list in a comment instead.",
    },
    "branch.line": {
        "pl": "🌿 Gałąź planu: `{branch}` · lokalnie {local} · na GitHubie {remote}",
        "en": "🌿 The plan's branch: `{branch}` · local {local} · on GitHub {remote}",
    },
    "branch.open_on_github": {
        "pl": "[otwórz na GitHubie]({url})",
        "en": "[open on GitHub]({url})",
    },
    "branch.commits": {
        "pl": "Na tej gałęzi jest już {count} commit(ów) z DevLoop: {hashes}.",
        "en": "This branch already holds {count} DevLoop commit(s): {hashes}.",
    },
    "branch.continues": {
        "pl": "Plan kontynuuje gałąź {count} wcześniejszego planu(ów) dla tego issue; ich commity i PR są wspólne.",
        "en": "This plan continues the branch of {count} earlier plan(s) for this issue; their commits and pull request are shared.",
    },
    "requirement.replan_note": {
        "pl": "Nowy plan trafi na istniejącą gałąź `{branch}` i do jej PR.",
        "en": "A new plan goes onto the existing branch `{branch}` and its pull request.",
    },
    "plan.files": {
        "pl": "📄 tworzy: {creates} · ✏️ zmienia: {modifies}",
        "en": "📄 creates: {creates} · ✏️ modifies: {modifies}",
    },
    "plan.continue": {
        "pl": "➕ Dokończ / rozszerz plan",
        "en": "➕ Finish / extend the plan",
    },
    "plan.continue_help": {
        "pl": "Zrobione zadania zostają. Planner dostaje to, co zrobione, i kod na gałęzi planu, i planuje tylko brakującą resztę; niedokończone zadania są zastępowane.",
        "en": "Done tasks stay. The planner is given what is done and the code on the plan's branch, and plans only what is missing; unfinished tasks are replaced.",
    },
    "plan.continue_spinner": {
        "pl": "🧠 Planner planuje brakującą resztę ...",
        "en": "🧠 The planner is planning what is missing ...",
    },
    "plan.continued": {
        "pl": "Plan rozszerzony: {added} nowe zadanie(a), {kept} zrobionych zostaje.",
        "en": "Plan extended: {added} new task(s), {kept} done task(s) kept.",
    },
    "plan.continue_failed": {
        "pl": "Nie rozszerzono planu: {reason}",
        "en": "The plan was not extended: {reason}",
    },
    "plan.split_hint": {
        "pl": (
            "Ten plan ma {count} zadań, czyli jeden duży PR. Jeśli "
            "części dają się oddać osobno, rozważ ✂️ Rozbij na issues "
            "przy wymaganiu."
        ),
        "en": (
            "This plan has {count} tasks, which is one large pull "
            "request. If parts can ship separately, consider ✂️ "
            "Split into issues on the requirement."
        ),
    },
    "revise.heading": {
        "pl": "🔁 Odeślij do poprawki",
        "en": "🔁 Send back for revision",
    },
    "revise.caption": {
        "pl": (
            "Developer poprawi istniejące pliki według "
            "wybranych uwag i Twoich notatek. Potem znów "
            "kompilacja, Architekt, QA i testy."
        ),
        "en": (
            "The Developer edits the existing files from the "
            "chosen findings and your notes, then compile, "
            "Architect, QA and tests run again."
        ),
    },
    "revise.findings": {
        "pl": "Uwagi Architekta do poprawienia",
        "en": "Architect findings to fix",
    },
    "revise.notes": {
        "pl": "Twoje uwagi dla Developera",
        "en": "Your notes for the Developer",
    },
    "revise.placeholder": {
        "pl": "Np. użyj /\\p{Ll}/u zamiast /[a-z]/, żeby działały polskie litery.",
        "en": "E.g. use /\\p{Ll}/u instead of /[a-z]/ so accented letters count.",
    },
    "revise.send": {
        "pl": "🔁 Odeślij do poprawki",
        "en": "🔁 Send back for revision",
    },
    "revise.running": {
        "pl": "🤖 Developer poprawia kod ...",
        "en": "🤖 The Developer is revising the code ...",
    },
    "revise.done": {
        "pl": "Poprawione. To nowa wersja zadania; poprzednia ma status REVISED.",
        "en": "Revised. This is the task's new version; the previous one is REVISED.",
    },
    "revise.failed": {
        "pl": "Nie udało się poprawić: {reason}",
        "en": "The revision failed: {reason}",
    },
    "revise.wrong_branch": {
        "pl": "Zadanie powstało na {branch}, a wybrana jest {current}. Przełącz się z powrotem.",
        "en": "The task was generated on {branch}, but {current} is checked out. Switch back first.",
    },
    "step.improve": {
        "pl": "Developer poprawił kod",
        "en": "Developer revised the code",
    },
    "step.qa": {
        "pl": "QA napisało testy",
        "en": "QA wrote the tests",
    },
    "plan.pr_line": {
        "pl": "🔀 PR planu: [{label}]({url}) · **{state}**",
        "en": "🔀 The plan's PR: [{label}]({url}) · **{state}**",
    },
    "ci.load": {
        "pl": "🧪 Sprawdź CI w PR",
        "en": "🧪 Check the PR's CI",
    },
    "ci.none": {
        "pl": "Brak checków CI na ostatnim commicie PR.",
        "en": "No CI checks on the PR's latest commit.",
    },
    "ci.failed_to_read": {
        "pl": "Nie odczytano CI: {reason}. Token potrzebuje uprawnienia Actions: Read-only dla tego repozytorium.",
        "en": "CI could not be read: {reason}. The token needs Actions: Read-only on this repository.",
    },
    "ci.heading": {
        "pl": "🧪 CI na {sha}: {passed} ok, {failed} nie, {pending} w toku",
        "en": "🧪 CI on {sha}: {passed} passed, {failed} failed, {pending} running",
    },
    "ci.log": {
        "pl": "Koniec logu: {name}",
        "en": "End of the log: {name}",
    },
    "ci.send": {
        "pl": "🔁 Odeślij tę porażkę do poprawki",
        "en": "🔁 Send this failure back for revision",
    },
    "ci.sent": {
        "pl": "Porażka „{name}” odesłana do {task}. Nowa wersja czeka na akceptację; po pushu CI uruchomi się ponownie.",
        "en": "The failure of '{name}' was sent back to {task}. The new version waits for approval; CI runs again after the push.",
    },
    "feedback.load": {
        "pl": "💬 Wczytaj uwagi z PR",
        "en": "💬 Load the PR's review comments",
    },
    "feedback.none": {
        "pl": "Brak nowych uwag w PR (pominięte: puste akceptacje, komentarze DevLoop i uwagi już odesłane).",
        "en": "No new review comments on the PR (left out: bare approvals, DevLoop's own, and those already sent back).",
    },
    "feedback.failed": {
        "pl": "Nie wczytano uwag z PR: {reason}",
        "en": "The PR's comments could not be read: {reason}",
    },
    "feedback.heading": {
        "pl": "💬 Uwagi z PR ({count})",
        "en": "💬 Review comments on the PR ({count})",
    },
    "feedback.caption": {
        "pl": "Zaznacz uwagi i wybierz zadanie, które ma je poprawić. Każde zadanie dostanie swoje uwagi jako notatki do rewizji; potem akceptujesz, wypychasz, a opis PR się odświeży.",
        "en": "Tick comments and pick the task that should address each. Every task gets its comments as revision notes; then accept, push, and the PR's description updates.",
    },
    "feedback.task": {
        "pl": "Zadanie",
        "en": "Task",
    },
    "feedback.send": {
        "pl": "🔁 Odeślij zaznaczone do poprawki ({count})",
        "en": "🔁 Send the ticked ones back for revision ({count})",
    },
    "feedback.spinner": {
        "pl": "🤖 Developer poprawia: {task} ...",
        "en": "🤖 The Developer is revising: {task} ...",
    },
    "feedback.done": {
        "pl": "Odesłano {count} uwag(i) do {tasks} zadań(nia). Nowe wersje czekają na akceptację.",
        "en": "Sent {count} comment(s) back to {tasks} task(s). The new versions wait for approval.",
    },
    "feedback.partial": {
        "pl": "Rewizja zadania {task} nie powiodła się: {reason}. Wcześniejsze odesłane uwagi zostały zapisane.",
        "en": "Revising task {task} failed: {reason}. Comments sent back before it are recorded.",
    },
    "plan.pr_refresh": {
        "pl": "🔄 Sprawdź stan PR",
        "en": "🔄 Check the PR",
    },
    "plan.pr_refreshed": {
        "pl": "{label}: {state}",
        "en": "{label}: {state}",
    },
    "plan.pr_none_pushed": {
        "pl": (
            "Gałąź planu jest wypchnięta, ale PR jeszcze nie "
            "istnieje — otwórz go z dowolnego zadania planu."
        ),
        "en": (
            "The plan's branch is pushed, but there is no PR "
            "yet — open it from any task of the plan."
        ),
    },
    "pr.synced": {
        "pl": "Wypchnięto {branch} i zaktualizowano opis {label}.",
        "en": "Pushed {branch} and updated the description of {label}.",
    },
    "pr.sync_failed": {
        "pl": (
            "Wypchnięto {branch}, ale opisu PR nie udało się "
            "zaktualizować: {reason}"
        ),
        "en": (
            "Pushed {branch}, but the PR description could "
            "not be updated: {reason}"
        ),
    },
    "step.branch": {
        "pl": "Gałąź planu",
        "en": "Plan branch",
    },
    "step.gates": {
        "pl": "Kontrole bez modelu (struktura, kompilacja)",
        "en": "Free checks (structure, compilation)",
    },
    "step.qa_refresh": {
        "pl": "QA przepisało testy zmienionych plików",
        "en": "QA rewrote the suites of changed files",
    },
    "step.usage": {
        "pl": "Zużycie tokenów i koszt",
        "en": "Token usage and cost",
    },
    "step.written": {
        "pl": "Zapisano plików na dysk",
        "en": "Files written to disk",
    },
    "step.types": {
        "pl": "Sprawdzono typy",
        "en": "Types checked",
    },
    "step.types_retry": {
        "pl": "Typy po poprawce",
        "en": "Types after a fix",
    },
    "types.heading": {
        "pl": "🧮 Kompilacja",
        "en": "🧮 Compilation",
    },
    "types.passed": {
        "pl": "🧮 Kod się kompiluje — bez błędów typów.",
        "en": "🧮 The code compiles — no type errors.",
    },
    "types.failed": {
        "pl": "🧮 Kompilacja odrzuciła kod — {summary}",
        "en": "🧮 Compilation rejected the code — {summary}",
    },
    "types.unavailable": {
        "pl": "🧮 Kompilator nie mógł działać: {reason}",
        "en": "🧮 The compiler could not run: {reason}",
    },
    "types.not_run": {
        "pl": "🧮 Kompilacji nie uruchomiono.",
        "en": "🧮 Compilation was not run.",
    },
    "types.errors": {
        "pl": "Błędy kompilatora ({count})",
        "en": "Compiler errors ({count})",
    },
    "tests.skipped_no_compile": {
        "pl": (
            "🧪 Testów nie uruchomiono, bo kod się nie "
            "kompiluje — każdy zestaw i tak nie dałby się "
            "wczytać."
        ),
        "en": (
            "🧪 Tests were not run because the code does "
            "not compile — every suite would fail to "
            "load anyway."
        ),
    },
    "step.tests": {
        "pl": "Uruchomiono testy",
        "en": "Tests run",
    },
    "step.tests_retry": {
        "pl": "Testy po poprawce",
        "en": "Tests after a fix",
    },
    # --------------------------------- requirement plans
    "requirement.status": {
        "pl": "Status: {state} · zaktualizowano {when}",
        "en": "Status: {state} · updated {when}",
    },
    "requirement.linked_plans": {
        "pl": "Powiązane plany ({count})",
        "en": "Linked plans ({count})",
    },
    "requirement.no_plans": {
        "pl": (
            "Brak planów. **🧠 Generuj plan** rozbije to "
            "wymaganie na zadania."
        ),
        "en": (
            "No plans yet. **🧠 Generate plan** breaks "
            "this requirement into tasks."
        ),
    },
    "requirement.plan_progress": {
        "pl": "{done}/{total} zadań · {state}",
        "en": "{done}/{total} tasks · {state}",
    },
    "requirement.open_plan": {
        "pl": "📋 Otwórz plan",
        "en": "📋 Open plan",
    },
    "issue.loaded": {
        "pl": "Wczytano {count} otwartych zgłoszeń.",
        "en": "Loaded {count} open issue(s).",
    },
    "issue.could_not_read": {
        "pl": "Nie udało się odczytać zgłoszeń: {reason}",
        "en": "Could not read issues: {reason}",
    },
    # ---------------------------------------- dashboard
    "board.total": {"pl": "Razem", "en": "Total"},
    "board.completed": {
        "pl": "Ukończone",
        "en": "Completed",
    },
    "board.running": {"pl": "W toku", "en": "Running"},
    "board.ready": {"pl": "Gotowe", "en": "Ready"},
    "board.blocked": {
        "pl": "Zablokowane",
        "en": "Blocked",
    },
    "board.failed": {
        "pl": "Nieudane",
        "en": "Failed",
    },
    # --------------------------------------------- task
    "task.details": {
        "pl": "Szczegóły zadania",
        "en": "Task Details",
    },
    "task.history": {
        "pl": "📜 Historia zadań",
        "en": "📜 Task History",
    },
    "task.none_yet": {
        "pl": "Brak zadań.",
        "en": "No tasks yet.",
    },
    "task.approve": {
        "pl": "✅ Akceptuj",
        "en": "✅ Approve",
    },
    "task.reject": {
        "pl": "❌ Odrzuć",
        "en": "❌ Reject",
    },
    "task.reject_committed": {
        "pl": (
            "Scommitowane jako `{hash}` — odrzucenie nie "
            "cofnie commita. Popraw to kolejnym zadaniem."
        ),
        "en": (
            "Committed as `{hash}` — rejecting would not "
            "undo the commit. Fix it with another task."
        ),
    },
    "task.score": {
        "pl": "Ocena architektury",
        "en": "Architecture Score",
    },
    "task.recommendation": {
        "pl": "Rekomendacja",
        "en": "Recommendation",
    },
    "task.review_iterations": {
        "pl": "Rundy recenzji",
        "en": "Review Iterations",
    },
    "task.scaffolding": {
        "pl": (
            "Ten przebieg utworzył rusztowanie projektu "
            "przed napisaniem kodu: {names}"
        ),
        "en": (
            "This run created the project scaffolding "
            "before writing any code: {names}"
        ),
    },
    # --------------------------------------------- tabs
    "tab.code": {"pl": "💻 Kod", "en": "💻 Code"},
    "tab.review": {
        "pl": "🏛 Recenzja architektury",
        "en": "🏛 Architecture Review",
    },
    "tab.structural": {
        "pl": "🏗 Ustalenia strukturalne",
        "en": "🏗 Structural Findings",
    },
    "tab.history": {
        "pl": "📜 Historia recenzji",
        "en": "📜 Review History",
    },
    "tab.tests": {"pl": "🧪 Testy", "en": "🧪 Tests"},
    "tab.files": {
        "pl": "📂 Wygenerowane pliki",
        "en": "📂 Generated Files",
    },
    "tab.diff": {
        "pl": "🔍 Przegląd zmian",
        "en": "🔍 Diff Review",
    },
    # ------------------------------------------- review
    "review.blockers": {
        "pl": "🚫 Blokery",
        "en": "🚫 Blockers",
    },
    "review.warnings": {
        "pl": "⚠️ Ostrzeżenia",
        "en": "⚠️ Warnings",
    },
    "review.suggestions": {
        "pl": "💡 Sugestie",
        "en": "💡 Suggestions",
    },
    "review.none": {
        "pl": "Brak recenzji architektury.",
        "en": "No architecture review available.",
    },
    "review.scope": {
        "pl": (
            "Projekt, granice i utrzymywalność. "
            "Problemy z plikami i importami są w "
            "Ustaleniach strukturalnych."
        ),
        "en": (
            "Design, boundaries and maintainability. "
            "File and import problems live in "
            "Structural Findings."
        ),
    },
    "review.no_history": {
        "pl": "Brak historii recenzji.",
        "en": "No review history.",
    },
    "structural.none": {
        "pl": "Nie znaleziono problemów strukturalnych.",
        "en": "No structural problems found.",
    },
    "structural.source": {
        "pl": (
            "Znalezione deterministycznym przebiegiem "
            "po wygenerowanych plikach, nie przez model."
        ),
        "en": (
            "Found by a deterministic pass over the "
            "generated files, not by the model."
        ),
    },
    # -------------------------------------------- tests
    "tests.execution": {
        "pl": "🧪 Wykonanie testów",
        "en": "🧪 Test Execution",
    },
    "tests.none": {
        "pl": "Brak dostępnych testów.",
        "en": "No tests available.",
    },
    "tests.never_run": {
        "pl": "Testy nigdy nie zostały uruchomione.",
        "en": "The tests were never run.",
    },
    "tests.not_run_warning": {
        "pl": (
            "🧪 Testy nie zostały uruchomione — "
            "przeglądasz nieprzetestowany kod."
        ),
        "en": (
            "🧪 Tests were not run — you are reviewing "
            "untested code."
        ),
    },
    "tests.incomplete": {
        "pl": "🧪 Przebieg testów nie zakończył się.",
        "en": "🧪 The test run did not complete.",
    },
    "tests.output": {
        "pl": "Wyjście testów",
        "en": "Test output",
    },
    "tests.passed": {"pl": "Zdane", "en": "Passed"},
    "tests.failed": {"pl": "Niezdane", "en": "Failed"},
    # --------------------------------------------- git
    "git.commit": {"pl": "Commit", "en": "Commit"},
    "git.branch": {"pl": "Gałąź", "en": "Branch"},
    "git.remote": {"pl": "Zdalne", "en": "Remote"},
    "git.remote_branch": {
        "pl": "Gałąź zdalna",
        "en": "Remote branch",
    },
    "git.commit_message": {
        "pl": "Treść commita",
        "en": "Commit message",
    },
    "git.commit_message_preview": {
        "pl": "Treść commita, która zostanie użyta",
        "en": "Commit message that would be used",
    },
    "git.approve_note": {
        "pl": (
            "Akceptacja zadania tworzy tę gałąź i "
            "commit. Nic nie jest wypychane."
        ),
        "en": (
            "Approving the task creates this branch and "
            "commit. Nothing is pushed."
        ),
    },
    "git.nothing_to_commit": {
        "pl": "Żadne pliki nie zostałyby zacommitowane.",
        "en": "No files would be committed.",
    },
    "git.push": {
        "pl": "⬆️ Wypchnij gałąź",
        "en": "⬆️ Push branch",
    },
    "git.push_note": {
        "pl": (
            "To wysyła gałąź do zdalnego repozytorium. "
            "Pull request nie jest tworzony."
        ),
        "en": (
            "This sends the branch to the remote. No "
            "pull request is created."
        ),
    },
    "pr.create": {
        "pl": "🔀 Utwórz pull request",
        "en": "🔀 Create pull request",
    },
    "pr.note": {
        "pl": (
            "To otwiera pull request. Nigdy nie jest "
            "scalany, zamykany ani komentowany."
        ),
        "en": (
            "This opens a pull request. It is never "
            "merged, closed or commented on."
        ),
    },
    "pr.heading": {
        "pl": "Pull Request",
        "en": "Pull Request",
    },
    "pr.description_preview": {
        "pl": "Opis, który zostanie użyty",
        "en": "Description that would be used",
    },
    # --------------------------------------------- diff
    "diff.added": {"pl": "Dodane", "en": "Added"},
    "diff.modified": {
        "pl": "Zmienione",
        "en": "Modified",
    },
    "diff.deleted": {"pl": "Usunięte", "en": "Deleted"},
    "diff.scope": {
        "pl": (
            "Co te pliki zmieniłyby w repozytorium. "
            "Tylko odczyt; nic nie jest zapisywane."
        ),
        "en": (
            "What these files would change in the "
            "repository. Reading only; nothing is "
            "written."
        ),
    },
    "diff.identical": {
        "pl": "Identyczne z wersją zacommitowaną.",
        "en": "Identical to the committed version.",
    },
    "diff.unavailable": {
        "pl": (
            "Brak tekstu różnicy; werdykt powyżej "
            "dotyczy tego, co było recenzowane."
        ),
        "en": (
            "No diff text available any more; the "
            "verdict above is what was reviewed."
        ),
    },
    "diff.no_repository": {
        "pl": (
            "To zadanie nie zapisało repozytorium, więc "
            "nie ma z czym porównywać."
        ),
        "en": (
            "This task did not record a repository, so "
            "there is nothing to compare against."
        ),
    },
    # -------------------------------------------- files
    "files.none_written": {
        "pl": "Dla tego zadania nie zapisano plików.",
        "en": "No files were written for this task.",
    },
    "files.none_generated": {
        "pl": "To zadanie nie wygenerowało plików.",
        "en": "This task generated no files.",
    },
    "files.no_code": {
        "pl": "Nie wygenerowano kodu.",
        "en": "No code generated.",
    },
    "files.no_source": {
        "pl": "Brak plików źródłowych.",
        "en": "No source files.",
    },
    "files.gone": {
        "pl": "Pliku już nie ma na dysku.",
        "en": "File not found on disk any more.",
    },
    "files.no_path": {
        "pl": (
            "To zadanie nie zapisało, gdzie trafiły "
            "jego pliki, więc nie można ich odczytać."
        ),
        "en": (
            "This task did not record where its files "
            "were written, so they cannot be read."
        ),
    },
    "files.unregistered": {
        "pl": (
            "Ten katalog nie jest już zarejestrowany "
            "jako repozytorium, ale jego pliki nadal "
            "dają się odczytać."
        ),
        "en": (
            "This folder is not registered as a "
            "repository any more, but its files are "
            "still readable."
        ),
    },
}


def translate(
    key: str,
    language: str = DEFAULT_LANGUAGE,
    **values: object,
) -> str:
    """One message, in one language.

    An unknown key returns itself in angle brackets rather
    than an empty string or a crash: a missing message
    should be obvious on the page, and the test suite will
    not let one reach a release anyway.
    """

    entry = MESSAGES.get(key)

    if entry is None:
        return f"⟨{key}⟩"

    text = entry.get(language) or entry.get(
        DEFAULT_LANGUAGE,
        f"⟨{key}⟩",
    )

    if not values:
        return text

    try:
        return text.format(**values)

    except (KeyError, IndexError):

        # A placeholder the caller did not supply. Showing
        # the unformatted text beats showing nothing.
        return text
