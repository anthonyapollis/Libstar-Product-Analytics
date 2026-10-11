# Employee 360 walkthrough

Computer-generated narration over the corrected slides. Not a voice clone or live screen recording.

## Slide 1: Purpose and evidence

Welcome to the Employee three sixty data quality walkthrough, prepared for Anthony Grant Apollis. This presentation explains the supplied data, the release decision, the reconciliation findings, and the evidence included in the submission.
The project compares three extracts: human resources, payroll, and the delivered Employee three sixty dataset. Each file contains forty eight rows. Equal row counts are only a starting point, because a missing employee and an unexpected employee can cancel each other out in the totals.
The solution combines profiling, explicit quality rules, field comparisons, monitoring, and an incremental loading demonstration. The objective is to make defects explainable and traceable before the data is released for reporting.
This video uses the corrected presentation and recorded dashboard evidence. The narrator is computer generated. It is a slide based explanation, not a live screen recording or a clone of Anthony's voice. The accompanying code and evidence allow a reviewer to inspect the implementation.

## Slide 2: Release decision and verified counts

The release decision is block. That is a business control outcome: the checks have identified problems that require investigation. It does not mean the pipeline crashed, or that every employee failed every check.
The corrected local validation returns seventeen rule findings across twelve employee identifiers. All ten controls detect at least one defect. Findings can overlap: one employee may violate several rules, and a stale record can appear in more than one source.
A final review found a status mapping error in the local implementation. A terminated employee with payroll marked Stopped is a consistent pair. The checker previously expected a different label and incorrectly flagged two valid pairs. That error has been corrected and a regression test now protects the mapping.
These local output rows must be read separately from the historical Databricks lifecycle figures shown later. The implementations do not have identical rule identifiers or aggregation. The package records that limitation rather than claiming complete result parity.

## Slide 3: Checks and salary risk

The assessment spans seven dimensions: uniqueness, completeness, referential integrity, consistency, validity, timeliness, and reconciliation. Ten controls cover these dimensions, with a severity and a release action attached to each result.
SQL is useful for readable profiling, joins, grouped checks, and dashboard queries. PySpark supports the distributed Databricks pipeline. The package also includes a local Python implementation for repeatable validation without requiring a cloud workspace.
One important business insight is that totals hide offsetting differences. The documented salary comparison shows a net difference of sixty four thousand six hundred rand, but a gross absolute difference of two hundred and twenty five thousand two hundred rand.
The net amount allows overstatements and understatements to cancel. The gross amount sums their magnitudes and exposes a larger reconciliation problem. Neither number is automatically a proven financial loss. Currency conflicts and unverifiable payroll values must be investigated before the figures are used for payment or reporting decisions.

## Slide 4: Reconciliation and root cause

The source comparison joins employee records on employee identifier. Payroll also has a pay period, so a comparison must select the relevant period before joining. Otherwise multiple payroll rows could multiply the comparison and create misleading results.
Employee E one zero two seven exists upstream but is missing downstream. Employee E one zero nine nine appears downstream without the expected source employee. Its match to E one zero two eight across eight tested attributes supports a copied record hypothesis. Confirming the exact upstream cause requires source system lineage.
The historical dashboard identifies six employees with field errors, covering attributes such as employment status, salary, currency, and other profile details. Employee E one zero one five has conflicting payroll values, so the outcome remains Cannot verify. Selecting an arbitrary value would hide the conflict.
Employee E one zero four two is a documented future dated HR exception. That difference is displayed for transparency and excluded from failure counts. The local checker has narrower field coverage than the historical dashboard; the packaged scope note explains why those results should not be treated as interchangeable.

## Slide 5: Incremental loads and lifecycle

The three run demonstration tests change handling. Run one loads the supplied files. In the historical dashboard it starts with seventeen open lifecycle issues. That count describes the dashboard's issue model, not the row count of every packaged output.
Run two presents the same files again. Matching file hashes allow the loader to skip an unchanged delivery, avoiding duplicate processing. An unchanged delivery does not resolve existing issues; they remain open until later evidence shows the problem has gone away.
Run three uses a separate, deliberately simulated delivery. It resolves eight earlier issues, introduces two new issues, and leaves eleven open. The arithmetic is seventeen, minus eight, plus two, which equals eleven.
Resolved means a later evaluated delivery no longer triggers that issue. It does not mean the original supplied files were repaired. The simulation proves that the lifecycle responds to changes. The local regression test independently verifies file hash changes and unchanged file skips; it does not claim to test streaming change data capture.

## Slide 6: Monitoring and failure investigation

The dashboard brings together the release decision, rule outcomes, affected employees, severity, and actions. Investigators can begin with a failing rule, identify the affected employee and source, and then inspect the record level evidence.
Severity and release action are separate fields. A rule may block release, require an immediate alert, or remain under monitoring. Review the configured action for the rule rather than assuming every critical or high severity result has the same response.
A technical failure is different. The earlier unsupported SQL subquery was an execution error, requiring an engineering fix. A successful job that reports failed data quality checks has completed its technical work and correctly exposed a business data problem.
For a failed run, inspect the run identifier, failed task, error message, input delivery, and last successful stage. For a data defect, follow the employee, source, and rule to the responsible data owner. Retry after an operational repair; release only after the relevant quality controls have been satisfied.

## Slide 7: Governance and cost conscious delivery

The design separates raw ingestion, conformed data, and reporting outputs through Bronze, Silver, and Gold layers. Run identifiers, source hashes, rule outcomes, and recorded evidence provide traceability. The ebook includes the data model and a join map to explain these relationships.
Governance also needs accountable owners, access controls, retention decisions, and an agreed response process. The private dashboard is documented as using workspace permissions. Production access and retention policies still require configuration in the deployment environment.
The optional dbt layer adds documented SQL models, dependency lineage, and reusable tests. Its local validation is recorded separately from Databricks execution. The Azure DevOps file defines a proposed continuous integration workflow; it is not evidence that a live production deployment has already occurred.
Before deployment, run regression tests and validate the rule changes. For scheduled processing, check changed inputs and use targeted queries where possible. Reserve full historical profiling for a periodic review or a material schema change. Route alerts to owners and suppress repeated unchanged alerts to reduce both compute cost and noise.

## Slide 8: Independent judgement and review route

AI assisted drafting and review, but its suggestions still needed testing. One rejected suggestion used a grouped first value to resolve conflicting payroll entries. That could silently select a salary and conceal an ambiguity. The chosen approach retains Cannot verify and preserves the evidence.
The final review also corrected the local payroll status mapping. These examples show why a passing script is not enough: the business meaning of the test must be checked, and the test suite must challenge both valid and invalid cases.
To review the submission, extract the ZIP into a new folder and open Start Here. Read the ebook, inspect the dashboard captures, and compare the machine readable outputs with the code. Run the supplied local tests using the documented commands. The manifest provides a checksum for each packaged file.
The remaining business action is to work with the source owners, correct confirmed defects in a controlled delivery, and rerun the controls. Only then should the release decision change. This concludes the walkthrough of the evidence, findings, implementation, and limitations.