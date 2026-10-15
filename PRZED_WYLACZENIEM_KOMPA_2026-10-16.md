# Co zrobiłem przed wyłączeniem kompa (noc z 15 na 16.10.2026)

Prosiłeś: zrób punkty 1–4 z #41, zacommituj, zostaw notatkę i wyłącz komputer
bez pytania. Wszystko jest na `main` i wypchnięte na GitHuba.

## Testy (#41, zamknięte)

1. **pytest** uruchamia wszystko:
   ```powershell
   .venv\Scripts\python -m pytest -n auto      # wszystko offline, równolegle, ~30 s
   .venv\Scripts\python -m pytest -m unit      # albo: integration, ui, e2e, browser
   .venv\Scripts\python -m pytest --live       # plus płatne testy na prawdziwym modelu
   ```
   Stare skrypty `tests/*_test.py` zostały skryptami. Pytest zbiera każdy jako
   jeden test i uruchamia go w osobnym procesie, z poziomem: `unit` (11),
   `integration` (27), `ui` (6), `live` (3, domyślnie pomijane).
   `tests/run_offline.py` dalej działa, CI go używa.
2. **Pokrycie kodu:** `python tests/coverage.py` mierzy każdy proces, który
   startują testy, łącznie z workerem. Daje podsumowanie i raport
   `coverage-html/index.html`. Wynik: **80%**.
3. **Test e2e całej ścieżki** (`tests/e2e/e2e_full_path.py`): issue na
   GitHubie → wymaganie → plan → run w tle → akceptacja tasków → push → PR →
   merge → DELIVERED, przeklikane przez prawdziwą stronę. Model jest
   skryptowany, GitHub to fałszywy serwer na localhost, a „remote” to repo
   bare na dysku. Z TypeScriptem pożyczonym z `datepicker-ts` działa
   prawdziwy `tsc` i Vitest.
4. **Test w prawdziwej przeglądarce** (`tests/e2e/e2e_browser.py`): Playwright
   z Chromium na prawdziwym serwerze DevLoop sprawdza:
   - stronę z wersją;
   - dodanie repozytorium;
   - zapis wymagania;
   - zmianę języka.

Wynik na koniec: **46 testów przeszło, 3 płatne pominięte**, około 30 s.

Do testów doinstalowałem do `.venv` pytest, pytest-xdist, coverage, playwright
i przeglądarkę Chromium. Lista jest w `requirements-dev.txt`.

## Wcześniej tego wieczoru

- **#39:** wywołania modelu w obrębie taska idą równolegle (pliki developera,
  testy QA). Koszt ten sam, task powinien być o około 1/3 szybszy.
- **#38:** pierwsze wydanie `v0.9.0` (alpha, pre-release) jako zablokowany tag
  plus GitHub Release. Wersjonowanie przez tagi, bez gałęzi.
- **#36–#37:** migracje bazy z kopią zapasową oraz numer wersji pod tytułem
  strony.
- **#35:** panel ⚙️ Ustawienia (klucze, limit, język; domyślnie angielski).
- **#20–#34:** issues założone wstecz dla wszystkiego z 15.10.

## Otwarte issues (plan na dalej)

- **#40:** pełne taski równoległe na `git worktree`, odłożone na po becie.
- **#42:** test e2e całej ścieżki nie jest wliczany do pokrycia, bo pod
  coverage numpy się wywala. Działa normalnie w każdym `pytest`.
  Przez to `ui/tasks.py` pokazuje tylko 12%.
- **#43:** mały płatny test na żywym modelu przed każdym wydaniem.

## Do zrobienia przez Ciebie

1. Przy następnym starcie DevLoop baza sama się zmigruje. Obok powstanie kopia
   `human_in_the_loop.db.v0.bak`, możesz ją zostawić albo usunąć.
2. Datepicker czeka na run, gdy będą kredyty: usuń `src` i `tests`
   w `C:\Projects\datepicker-ts`, zacommituj szkielet w Kroku 0, potem
   ⏩ Uruchom cały plan. Szacunek to około $0.48.
3. Możesz ustawić miesięczny limit w ⚙️ Ustawieniach, np. na wysokość salda API.

## Komputer

Po commicie tej notatki wyłączyłem komputer poleceniem
`shutdown /s /t 60`, tak jak prosiłeś. Minuta zwłoki jest po to, żeby git
i edytor zdążyły zapisać pliki.
