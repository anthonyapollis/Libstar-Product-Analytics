# AI use

## Tools and what they sped up
- **Claude Code (Anthropic)** drafted the Spark SQL, the PySpark reconciliation, the local Spark runners,
  the incremental notebook and these notes. It also ran everything locally and on Databricks.
- **Codex (OpenAI)** reviewed the branch independently (`CODEX_REVIEW.md`).
- **Fastest gains:** boilerplate (typed staging, `stack()` null profiling, Delta `MERGE` syntax), the local test
  harness and first drafts of the write-up.
- **Not delegated:** deciding what is an error and what is a legitimate exception, severity and ownership.
  These come from reading the data against the brief's ownership rules.

## AI-generated work that was wrong, and how it was caught
All three were caught by verification steps in this repository, not by trusting the output.

1. **A silent pass in the reconciliation.**
   - **The bug:** the first PySpark version took payroll's salary with `groupBy().agg(F.first(...))`. `first()`
     after a shuffle is **non-deterministic** in Spark. It also let E1015 pass: Employee 360 happened to match
     one of the two conflicting payroll salaries.
   - **How it was caught:** the independent pandas profile listed E1015 as a salary conflict, but Spark reported nothing.
   - **The fix:** take the value by explicit file order (`row_number()` in `00_staging.sql`) and add a
     **Cannot verify** class whenever payroll holds more than one value.
2. **A wrong claim about totals.** The first draft of the totals query said the salary difference was "less than
   0.3%". The totals already profiled showed R64,600 (2.6%). The section was rewritten to show net (R64,600) against gross (R225,200)
   per employee, which makes the point better than the original claim did.
3. **SQL that only runs on one engine.** The look-alike query used `QUALIFY`. It is valid on Databricks but not in
   open-source Spark, so it failed the local run that CI depends on. It was rewritten with a ranked subquery,
   so one SQL file runs in both places.

*Your own example:* in the video, add one challenge you made yourself. For example, whether E1029's
"Payable" is an error or legitimate September pay (see findings §2), or whether E1042's future date
should fail the check.

## How the results were verified
- **An independent check in plain Python** (`tests/check_expected.py`) recomputes every rule's affected IDs from
  the CSVs with separately written logic and compares them with the Spark output: **10/10 rules agree**.
- **The same SQL and notebook ran on Databricks serverless and on local PySpark.** The results were compared
  line by line (`evidence/databricks_run.md`).
- **Every finding in `docs/findings.md` points to an output file and an employee ID**, so it can be checked by hand.

## Was it commercially justified?
- **Yes, for the parts that are mechanical and checkable:** SQL and PySpark scaffolding, the test harness and drafts.
- **No time was saved on judgement**, and some was spent verifying. The first example shows why: unverified
  AI output would have reported a salary as correct when it could not be known.
- **The cost:** a subscription, plus a reviewer's time. The second reviewer (Codex) is only worth it because it
  checks the outputs, not just the code.

## Confidentiality
The data is synthetic. With real client HR or payroll data, I would not paste records into a public AI tool. I
would use the client-approved assistant inside their tenancy, or work from schemas and synthetic samples only.
