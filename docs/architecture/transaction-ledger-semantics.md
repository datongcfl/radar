# M13 Architecture Decision: Transaction and Ledger Semantics

Status: proposed for implementation  
Scope: generic business transaction model and source-adapter contract  
Constraints: standard-library core; no ERP-specific runtime dependency; preserve source Evidence and exact row identity.

## Context

The first transaction-aware aggregation pass distinguishes posted receipts, physical returns, non-posted documents, duplicate imports, and returns linked to an exact original receipt item. It still operates on document-level quantity observations. That is not sufficient for inventory valuation or accounting reconciliation.

A business document and its ledger effects are different facts:

- A Purchase Receipt describes a physical receipt and may create Stock Ledger and interim accounting entries.
- A Purchase Return reverses physical stock movement and must reference the original receipt and item row.
- A Debit Note reverses supplier-bill / payable effects. It is not a physical return unless its own workflow explicitly updates stock.
- A cancellation may preserve original ledger rows and add reversing rows. Treating every cancelled source document as if no ledger effect ever existed loses the audit trail.

Radar must represent these independently and must not infer one ledger from another.

## Decision

Introduce a source-neutral transaction-ledger contract before implementing inventory-value aggregation.

### 1. Separate document lifecycle from ledger effects

A source adapter must not collapse document status and ledger posting status into one field.

Document lifecycle examples:

- draft
- submitted / posted
- cancelled
- amended

Ledger effect examples:

- original posting
- return posting
- cancellation reversal
- adjustment
- reposted valuation / accounting correction

A cancelled document may have both an original posting and one or more reversal rows. For ledger aggregation, include the actual ledger effects and apply their signed values. Do not simply discard all rows because the originating document is now cancelled. For document-level quantity aggregation, only explicitly eligible posted source documents may contribute.

### 2. Canonical ledger effect

The adapter should normalize source records into a common shape. Fields are optional only when the source system genuinely does not provide them; missing reconciliation-critical fields make the affected result unresolved.

| Field | Meaning |
| --- | --- |
| `ledger_entry_id` | Stable identity of this ledger row |
| `source_system` | Source adapter identifier |
| `ledger_kind` | `stock` or `general_ledger` |
| `company_id` | Legal entity / company boundary |
| `voucher_type`, `voucher_id` | Source business document identity |
| `voucher_item_id` | Exact source document row identity |
| `event_kind` | receipt, return, transfer, issue, invoice, debit_note, reversal, adjustment, etc. |
| `posting_status` | Whether this ledger row is an effective posting or reversal |
| `posting_at` | Source posting timestamp |
| `reversal_of` | Exact original ledger-entry reference, when this is a reversal |
| `source_document_ref` | Source document and item references |
| `item_id`, `warehouse_id` | Inventory dimensions, for stock ledger rows |
| `quantity_delta`, `quantity_uom` | Signed physical quantity effect |
| `stock_value_delta` | Signed inventory value effect from the stock ledger |
| `account_id` | General-ledger account, for GL rows |
| `debit_amount`, `credit_amount` | Original GL debit and credit values |
| `currency`, `company_currency` | Transaction and accounting currency context |
| `dimensions` | Project, cost center, business unit, and configured dimensions |
| `evidence_id`, `locator` | Exact source Evidence and row/cell locator |

The adapter must preserve the original source fields and provenance alongside normalized values. A normalized field without an Evidence locator is not sufficient for a verified assessment.

### 3. Inventory valuation must use ledger facts

For inventory valuation, use the stock ledger's actual signed value movement (for example, a source field equivalent to `stock_value_difference`) as the primary fact. Preserve quantity delta, valuation rate, valuation method, warehouse, item, posting order, and any serial/batch dimensions where available.

Do not universally recompute stock value as:

`quantity × purchase document rate`

That formula can be wrong when the source uses moving average, FIFO, standard cost, landed costs, rejected-material valuation rules, serial/batch valuation, precision rounding, or valuation reposting.

Document-level original receipt rates remain useful evidence and a validation reference, but they are not a substitute for the actual stock-ledger value movement.

### 4. Physical returns and supplier credits are separate event streams

- A physical Purchase Return contributes a negative stock quantity and the source system's actual stock-value delta.
- A Debit Note contributes to supplier payable / invoice accounting.
- A Debit Note must not reduce physical stock unless its own source record explicitly posts a stock movement.
- If a workflow creates both a Purchase Return and a Debit Note, Radar must retain both and must not count either one twice in the other's ledger.
- The return must link to the exact original receipt header and item row. Item, company, UOM, warehouse, serial/batch and other configured dimensions must be checked when the source provides them.

### 5. Reconcile stock ledger to the correct GL accounts

A stock-to-GL comparison is valid only after the adapter provides an explicit account mapping and compatible aggregation dimensions.

At minimum, reconciliation scope must preserve:

- company
- accounting period / posting cutoff
- currency
- inventory account or configured account mapping
- item / warehouse / project dimensions where the GL source actually supports them

Do not compare stock value to supplier payable, GRNI / Stock Received But Not Billed, or purchase expense indiscriminately. A purchase receipt may post inventory against a receipt-accrual account; the later invoice clears that accrual and creates payable. A Debit Note changes supplier accounting, not necessarily inventory.

The comparison must declare sign convention, account inclusion/exclusion, rounding precision, and tolerance. Missing account mapping or incompatible dimensions must produce an unresolved reconciliation, not a pass.

### 6. Return quantity cap is a first control, not the complete eligibility rule

The current R88 implementation rejects all returns linked to an original receipt item when their cumulative quantity exceeds that item's recorded receipt quantity. It deliberately does not choose an arbitrary subset of returns.

This remains a conservative first bound. A production-grade eligible-return calculation may also need:

- prior accepted and rejected quantities;
- current warehouse stock and transfers;
- serial / batch identity;
- earlier returns and reversals;
- unit-of-measure conversion and precision;
- source-specific returnable-quantity rules.

Until these are available, Radar must label the quantity result as a document-level cap, not proof that the physical goods are currently returnable from the selected warehouse.

## Invariant and assessment implications

The following checks should be independently computable and separately evidenced:

1. `return_not_over_received`: cumulative returns do not exceed the eligible quantity of the exact original receipt item.
2. `stock_ledger_quantity_balance`: signed stock quantity effects reconcile to the expected inventory movement.
3. `stock_ledger_value_balance`: stock value movement is internally consistent with source ledger effects.
4. `inventory_gl_value_reconciliation`: inventory value reconciles to the explicitly mapped inventory GL accounts at the declared scope.
5. `ledger_reversal_balance`: a cancellation reversal references the original ledger entry and reverses its applicable quantity/value/accounting effects within source precision.
6. `physical_return_debit_note_separation`: supplier-credit records do not masquerade as physical stock returns.

An aggregation with skipped, conflicting, unlinked, or unverified ledger rows is incomplete. Its numeric subtotal must not be promoted to a passing Assessment. Assessment must distinguish at least pass, fail, incomplete, and no_evidence.

## Adapter responsibilities

Each source adapter must declare:

- source document and ledger object types;
- exact identity fields and stable row references;
- document lifecycle and ledger posting-state mappings;
- reversal / amendment linkage;
- quantity and currency precision;
- stock-value and GL amount fields with sign conventions;
- account mapping and reconciliation dimensions;
- valuation method and any source-specific eligibility constraints;
- Evidence locators and source verification metadata.

The core engine consumes the normalized contract. It does not import ERPNext, Frappe, or any other ERP library.

## Acceptance tests before calling this complete

- receipt 10, returns 6 + 5 against the same original item: all returns for that target are unresolved as over-limit; no arbitrary partial acceptance;
- receipt 10, returns 6 + 4: net quantity is zero;
- two original receipt rows for the same item on different receipt documents: returns remain isolated by exact receipt/item identity;
- Debit Note without stock update: no stock quantity or stock value movement;
- Debit Note with explicit stock update: stock effect is read from its stock ledger rows, not inferred from the document type;
- cancelled voucher with original and reversal ledger rows: net effect is zero while both rows remain traceable;
- missing reversal target, account mapping, currency, or source locator: incomplete/unresolved;
- FIFO, moving-average, standard-cost, landed-cost and rejected-warehouse fixtures: stock-value delta comes from the ledger and is not recomputed from document rate;
- stock value and GL values reconcile only after explicit account mapping, scope alignment, and precision handling.

## Reference behavior used to inform this decision

The following ERPNext material is used as a behavioral reference, not as code to copy or a dependency to adopt:

- Purchase Return documentation: physical return references the original Purchase Receipt and uses negative quantities; Debit Note is a separate supplier-bill reversal.
- Purchase Receipt documentation: accepted and rejected quantities may post to different warehouses; perpetual inventory creates interim stock accounting.
- Immutable Ledger documentation: cancellation retains original rows and records reversals.
- Standard Valuation Rate documentation: stock valuation can differ from purchase document rate.
- Stock Ledger implementation: return valuation depends on valuation method and source context, reinforcing the need to consume actual ledger effects.

No ERPNext or GPL implementation code is copied into Radar by this decision.
