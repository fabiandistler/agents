# 2026-11-20 maintenance cadence

The question on 2026-11-20: would maintenance runs more often than about
weekly pay off? A chief-of-staff subagent gathered the evidence that morning,
read-only. It read the scheduled tasks (`list_triggers`, `get_session`), the
GitHub PR and issue APIs, the run records and reports under `maintenance/` on
each repo's `main`, and `maintenance-runs.py due`. A simulation replayed the
pick rule week by week, assuming each PR merges on its run day. The report
lived in a session scratchpad and is not kept. Decisions taken on it:
[2026-11-20 decisions](../decisions/2026-11-20-decisions.md).

- Tags kept from the report: **[read]** = from a tool result, file or API
  response; **[inferred]** = computed or deduced from read data. "Yield"
  follows repo-maintenance#164: a run yields if an issue filed from its report
  was closed by a merged PR, or if its own change PR merged.
- Skill line numbers: `plugins/repo-maintenance/skills/maintenance-run/SKILL.md`
  at `fabiandistler/repo-maintenance@bacc59d`.

## Capacity

One scheduled slot a week per repo [read]:

| Repo | Scheduled task, slot | Slots that gave a PR |
|------|----------------------|----------------------|
| agents | `trig_016FpvZkZFm5tPdbFCrXebbT`, Sun 01:34 Europe/Berlin | 5 of 6 since 2026-10-08 |
| repo-maintenance | `trig_01XPRmF1GFqjd1qFoWGvCi1G`, Mon 08:32 Europe/Berlin | 1 of 3 (2026-11-02 gave #109) |
| dotfiles | `trig_01XtaNXwvNSQbiDAZJq2vBPV`, Sun 01:36 UTC | 3 of 3 since its catalog landed 2026-10-26 |

- agents 2026-11-01 gave no PR although doc-drift was due (score 1.7), cause
  unrecorded [read]. repo-maintenance 2026-11-09 was probably a no-op, no job
  scoring ≥ 1 [inferred]; 2026-11-16 gave none while deps-audit and doc-drift
  were due ([runs without a trace](../problems/runs-without-trace.md)).

Job runs including off-schedule ones [read: counts; inferred: rates]:

| Repo | Job runs | Off-schedule |
|------|----------|--------------|
| agents | 11 in 6.1 weeks since 2026-10-08 (1.8/week) | 6 |
| repo-maintenance | 13 in 6.1 weeks (2.1/week); newest record 2026-11-07 | 12 |
| dotfiles | 6 in 3.4 weeks since 2026-10-27 (1.75/week) | 3 |

- No run was started by hand in agents after 2026-11-10, so capacity fell to
  the scheduled slot [read]. The scheduled-task minimum interval is normally
  one hour [read: tool contract], so it does not stop 2–3 runs a week.
- Shared budget [read]: one subscription serves the implementer, the
  chief-of-staff session with its subagents and its cloud sessions
  ([shared usage limit](../problems/shared-usage-limit.md)). The weekly limit
  resets Saturday 22:00 Berlin, and the maintenance slots fall right after.
  Thursday-evening runs of other tasks failed at the limit (prompts of
  `trig_015f62BX8xxGexeqvTa788k6`, `trig_0154VzngxBUhyhQ3gArfV6Ep`), so a
  late-week slot would land where other tasks ran out [inferred].

## Demand

D = runs a week the cooldowns ask for, C = 1 run a week; the simulated worst
score is after 8 weeks at C [inferred]:

| Repo | D (runs/week) | D/C; simulated worst score |
|------|---------------|----------------------------|
| agents | 2.97 | 3.0; 3.0 |
| repo-maintenance | 2.23 (3.43 before four jobs were retired 2026-11-14, repo-maintenance#147, #158) | 2.2; 3.0 |
| dotfiles | 3.43 (8 jobs) | 3.4; 2.5 |

- Pick rule [inferred]: relative overdueness keeps any job from starving but
  does not shrink the backlog; with D > C each job runs at about cooldown ×
  D/C. Simulated intervals at C: agents deps-audit about every 21 days,
  doc-drift, dead-exports and error-edges at most once in 8 weeks;
  repo-maintenance deps-audit about every 17.5 days, doc-drift and error-edges
  about every 35; dotfiles 7 of 8 jobs due after 8 runs, deps-audit about
  every 28 days.
- Realized in agents [read]: deps-audit 23 and 15 days apart (cooldown 7),
  doc-drift 31 (14), dead-exports 30 (14), error-edges 28 (14); scores at pick
  2.0–2.21 (#708, #719, #729, #851).
- Due on 2026-11-20 [read: `due --today`]: agents test-flakiness (1.13),
  which is also its 2026-11-22 pick and has zero yield so far;
  repo-maintenance deps-audit (2.00) and doc-drift (1.43); dotfiles 6 of 8.
  dotfiles picks semantic-duplication on 2026-11-22 and asset-drift on
  2026-11-29 (both never run); deps-audit waits until 2026-12-06 at the
  earliest, at a score of about 5.7 [inferred].

## Yield

Runs with yield / runs, per job [read; some issue-to-fix links inferred from
branch names and titles]:

| Repo | Jobs |
|------|------|
| agents | deps-audit 1/3, doc-drift 2/2, error-edges 1/2, dead-exports 0/2, test-flakiness 0/1, perf-quickwins 0/1 |
| repo-maintenance | deps-audit 3/3, doc-drift 2/2, error-edges 2/2, asset-drift 1/1, dead-exports 1/2, test-flakiness 0/1, perf-quickwins 0/1, semantic-duplication 0/1 (the last four retired 2026-11-14) |
| dotfiles | deps-audit, doc-drift, error-edges, perf-quickwins and test-flakiness 1/1 each; dead-exports 0/1; semantic-duplication and asset-drift never ran |

- Samples are tiny, 1–3 runs per job. Across the repos: deps-audit 5/7,
  doc-drift 5/5, error-edges 4/5 [read / inferred].
- 30 job-run PRs since 2026-10-08, all merged, none closed unmerged [read].
  Open to merge [inferred from read timestamps]: median 2.9 h, 11 within 1 h,
  9 over 8 h; agents 8.7 h (n=11), repo-maintenance 0.6 h (n=13), dotfiles
  3.9 h (n=6). Overnight PRs waited for a morning batch.
- Auto-merged: 0 of 30. The maintainer merged all 6 sampled PRs [read], the
  rest [inferred].
- Downstream load [read]: agents' error-edges run of 2026-11-10 filed #730–#734,
  and 5 fix PRs merged that day. repo-maintenance's `maintenance-pr-review.yml`
  runs one Claude review on every maintenance PR.

## Cost

Sampled runs [read: `get_session`; only sessions whose ids appear in PR
bodies could be sampled]:

| Repo | Sonnet | Opus |
|------|--------|------|
| agents | 2026-11-08 $0.50, 8 min; 2026-11-10 $0.72, 7 min | 2026-11-15 $2.37, 18 min |
| repo-maintenance | none | 2026-11-02 $1.45, 10 min; 2026-11-16 (no PR) $0.88, 2.4 min |
| dotfiles | 2026-11-08 $0.52, 2 min | 2026-11-15 $1.56, 4 min |

- Runs used 90–125k context tokens; the 2026-11-16 run that delivered
  nothing still used 90k [read].
- The agents and dotfiles tasks pinned no model and got the account default:
  Sonnet on 2026-11-08 and -10, Opus on 2026-11-15 [read]. Opus cost about
  2.7× Sonnet per run on the means ($1.56 vs $0.58) [inferred]; job mix and
  dates are confounded, and no job ran on both models.
- At the decided cadence on Opus: agents about $2.4 a week, dotfiles at 2 runs
  a week about $3.1, plus the review and implementer work a yielding run
  triggers [inferred].
- Not measured: the maintenance share of the 5-hour and weekly limits; the
  cost of runs before 2026-11-02; why the agents slots of 2026-10-28 and
  2026-11-01 gave no PR.

## Levers, as weighed on 2026-11-20

1. **More runs** (2–3 a week per repo). For: the simulated worst score after
   8 weeks fell to 1.3–1.8 at 2 a week and 1.0–1.2 at 3 [inferred]; a run
   costs $0.50–$2.37 [read]. Against: each yielding run adds review and
   implementer work on the shared budget; merging is manual and the cooldown
   starts at merge (SKILL.md step 5), so early runs become skips or no-ops;
   extra slots go first to zero-yield or never-run jobs [read];
   repo-maintenance's slot gave a PR 1 of 3 times.
2. **Retire zero-yield jobs.** For: agents' dead-exports, test-flakiness and
   perf-quickwins meet the yield rule, and retiring them cuts D from 2.97 to
   2.0 [inferred]; repo-maintenance did so on 2026-11-14 (#147: 39 % of runs
   for one `.pyc` removal) [read]. Against: tiny samples; dotfiles'
   perf-quickwins yielded (dotfiles#69, fixed by dotfiles#70); D/C stays about
   2.0–2.2 [inferred]; the agents and dotfiles catalogs lack the yield rule
   until the 2026-12-01 review [read].
3. **Longer intervals.** For: jobs already run at 1.4–3× their cooldown with
   no reported harm, and Dependabot covers the action pins weekly [read].
   Against: deps-audit and error-edges yield most, and longer cooldowns delay
   exactly them; it changes how overdue jobs look, not how many get done.
4. **More than one job per run.** For: a session pays a fixed cost for clone,
   baseline and skill reading [read / inferred]. Against: it breaks the
   skill's core rule (SKILL.md:16, :337, Rule 1 of every catalog) [read]; the
   maintainer merges as many PRs, and one failure loses both jobs [inferred].
5. **Fix reliability first.** For: the live agents and dotfiles prompts differ
   from the versioned bootstrap and pin no model, so cost swings about 3×
   [read]; each extra run multiplies these failure modes [inferred]. Against:
   those two slots already deliver, so D/C stays 3.0 and 3.4 [inferred].

Related: [schedules](../schedules.md),
[2026-11-20 status sweep](2026-11-20-status.md).
