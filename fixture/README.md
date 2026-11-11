# The fixture org

A small SFDX project that is the linter's corpus: one agent (`Service_Agent`), four topics,
seventeen actions, thirteen Apex classes and five Flows. It is committed source, not a download, so
every number in the repository can be reproduced offline with `afcl lint fixture`.

`EXPECTED_DRIFTS.json` is the ground truth. Every drift below was planted deliberately, one per
class, and the test suite asserts the linter reports exactly this set.

## What is planted, and where

| Action | Target | Planted | Where to look |
| --- | --- | --- | --- |
| Get_Case_Status | CaseStatusLookup (Apex) | nothing: a decoy. Apex label `Case Number`, schema title `Case record number`; name and type agree | `classes/CaseStatusLookup.cls`, `input/schema.json` |
| Create_Case | CaseCreator (Apex) | nothing, clean | |
| Send_Survey | Send_Survey (Flow) | nothing, clean | |
| Escalate_Case | Escalate_Case (Flow) | `priorityLevel` is a Number with scale 2 in the Flow and `lightning__integerType` in the schema | `flows/Escalate_Case.flow-meta.xml` |
| Summarize_Case | CaseSummarizer (Apex) | `caseId` is `Id` in Apex and `lightning__textType` in the schema | `classes/CaseSummarizer.cls` |
| Track_Shipment | ShipmentTrackerV2 (Apex) | the class does not exist; `ShipmentTracker` does | `genAiFunctions/Track_Shipment` |
| Get_Order_History | OrderHistoryService (Apex) | schema input `includeCancelled` has no Apex variable | `input/schema.json` |
| Cancel_Order | Cancel_Order (Flow) | Flow input `cancellationReason` is not in the schema | `flows/Cancel_Order.flow-meta.xml` |
| Update_Contact_Preferences | ContactPreferenceUpdater (Apex) | `channel` is `required=true` in Apex and present in the schema but not in its `required` list | `input/schema.json` |
| Log_Interaction | InteractionLogger (Apex) | `channel` is `required=true` in Apex and has no schema property at all | `input/schema.json` |
| Find_Similar_Cases | SimilarCaseFinder (Apex) | no output property is marked `copilotAction:isUsedByPlanner` | `output/schema.json` |
| Get_Account_Health | AccountHealthScorer (Apex) | schema output `riskLevel` is never produced | `output/schema.json` |
| Draft_Customer_Reply | ReplyDrafter (Apex) | `extraContext` declares `maxLength` 2000 against a documented cap of 250 | `input/schema.json` |
| Lookup_Product_Specs | Lookup_Product_Specs (Flow) | the Flow is in Draft status | `flows/Lookup_Product_Specs.flow-meta.xml` |
| Schedule_Callback | Schedule_Callback (Flow) | undecidable: `caseRecord` is an SObject variable | `flows/Schedule_Callback.flow-meta.xml` |
| Merge_Duplicate_Contacts | ContactMerger (Apex) | undecidable: `primary` is a `Contact` | `classes/ContactMerger.cls` |
| Reopen_Case | CaseReopener (Apex) | no topic lists it | `genAiPlugins/` |
| (topic) Order_Support | | lists `Apply_Discount`, which is not an action | `genAiPlugins/Order_Support.genAiPlugin-meta.xml` |

`SummaryUtil` is a helper class with no `@InvocableMethod`; it exists so the "class present but
not invocable" path of `missing_target` has something real to refuse.

## What the fixture is not

It has never been deployed to an org. The Apex compiles by inspection, the Flows are the minimal
XML an autolaunched Flow needs, and none of it has run. Which of these drifts the platform's own
deploy would reject is therefore not observed here; see ADR-005.
