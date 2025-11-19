1\. We have:



* A static SQLite relational database (Olist e-commerce dataset).
* Good number of tables:
* orders, order\_items, order\_payments, customers, sellers, products, reviews, etc.



2\. What we want to build:

An Anomaly Agent System with three components:



A) Data Simulation Layer



* Because the Olist data is static, we will inject anomalies artificially.
* We’ll write 4–5 scripts that:
* 
* Insert NEW rows
* Modify existing rows
* Create unusual spikes/drops
* Create data-quality issues
* All inside the same SQLite database.





B) Detection Layer (Anomaly Agent)



* This will run some logic and check:
* KPI spikes/drops
* Trend or cadence breaks
* Data quality issues
* Uses SQL or Python logic to detect the injected anomalies.
* Writes the findings into an Audit Table that we design.





C) Visualization Layer (Grafana / Superset)



* Connect Grafana or Superset directly to the SQLite DB.
* Build dashboards for:
* Anomalies from the audit table
* KPIs (orders, revenue, delivery time, cancellations, etc.)
* Time-series panels with anomaly flags





&nbsp;                  +-------------------+

&nbsp;                  |  SQLite Database  |

&nbsp;                  | (Olist + Injected |

&nbsp;                  |   data + Audit)   |

&nbsp;                  +-------------------+

&nbsp;                            ▲

&nbsp;                            │

&nbsp;   +-------------------+    │    +---------------------+

&nbsp;   |  Injection Script |----┘    |   Anomaly Agent     |

&nbsp;   | (4-5 scripts)     |         |  (Detection Logic)  |

&nbsp;   +-------------------+         +---------------------+

&nbsp;                                        │

&nbsp;                                        ▼

&nbsp;                         +---------------------------+

&nbsp;                         |       Audit Table         |

&nbsp;                         +---------------------------+

&nbsp;                                        │

&nbsp;                                        ▼

&nbsp;                         +---------------------------+

&nbsp;                         |   Grafana / Superset      |

&nbsp;                         |   (Charts + Anomalies)    |

&nbsp;                         +---------------------------+





------------------------



1\) Restating alignment (short)



* Single SQLite file with full Olist relational schema.
* This POC must be solid/marketable — not toy-level.
* The agent detects both business and data-quality anomalies.
* Dashboards show KPIs + anomaly overlays.
* Detection uses simple interpretable rules plus a couple of non-ML advanced rules (robust stats / seasonality), but no heavy ML.







2\) KPI \& anomaly checklist (prioritized — start here)



* Core KPIs (platform / global; daily grain)
* Orders: orders\_count\_daily
* Revenue: gross\_revenue\_daily (or payment\_value sum)
* Avg Order Value: avg\_order\_value\_daily
* Delivered orders \& delivery rate: delivered\_count\_daily, on\_time\_delivery\_rate
* Cancellations: cancellations\_count\_daily, cancellation\_rate
* Reviews: reviews\_count\_daily, avg\_review\_score
* Payment: payment\_type\_distribution, avg\_installments
* Data-quality: null\_ratios (critical cols), orphan\_counts, negative\_value\_counts



Per-dimension KPIs (drilldowns for anomalies)

* By seller\_id (top N sellers)
* By product\_category
* By customer\_state (geography)



Anomalies to detect (POC should cover all of these)

* Volume spike / drop (orders)
* Revenue spike / drop (gross revenue)
* AOV shifts (avg order value)
* Delivery delays spike / on-time rate drop
* Cancellation surge (overall or by seller)
* Review score collapse / surge in low-star %
* Payment-type distribution shift (e.g., credit\_card → boleto)
* Data-quality: sudden nulls, orphan records, negative/zero money values







3\) Detection approach (simple → enhanced, explainable)



A. Simple rule-based (primary POC)



* Rolling-window percent change vs baseline:

&nbsp;	Baseline = day-of-week-aware 7-day rolling median.

&nbsp;	Percent diff and absolute diff thresholds (e.g., >100% high spike).

* Minimum-volume filter (suppress when baseline < X).
* Persistence rule: require N runs for medium severity; immediate for high severity.
* Data-quality thresholds: null\_ratio > 5% → WARNING; >20% → HIGH.



B. Robust-statistics (advanced, non-ML)



* Rolling median + MAD z-like score to avoid influence of prior outliers.
* Day-of-week baselines (compare Mondays to recent Mondays).
* Optional: short Prophet/ETS forecast for key metrics only (if you want a second opinion later).



C. Aggregation \& grouping rules



* If multiple correlated metrics spike simultaneously (orders \& revenue), collapse into a composite event with linked sub-events.
* For per-seller checks: require higher min-volume or aggregate low-volume sellers to region-level.



D. Explainability



* Every anomaly row must include baseline\_method, baseline\_window, diff\_pct, diff\_abs, top contributors (sample sellers/products) — makes it demo-friendly.





5\) Audit schema (concise)



Keep it simple and query-friendly — 3 logical tables:



detection\_runs

* run\_id, start\_ts, end\_ts, trigger, status, checks\_executed, anomalies\_detected, notes



anomaly\_checks\_audit



* check\_id, run\_id, metric\_name, time\_window\_start, time\_window\_end,
* aggregation\_level, dimension\_value,
* metric\_value, baseline\_value, diff\_abs, diff\_pct, z\_like,
* baseline\_method, baseline\_window, thresholds\_used, evaluation\_status, details\_json, suppressed\_reason



* anomaly\_events
* anomaly\_id, check\_id, run\_id,
* anomaly\_type, severity, status (OPEN/ACK/RESOLVED),
* title, summary, time\_window\_start/end, metric\_name, metric\_value, baseline\_value, diff\_pct, dimension\_value, details\_json, detected\_at, ack\_by, ack\_at





6\) Dashboard layout (Grafana / Superset)



Keep 1 main dashboard for the demo, with drilldowns:



Top (KPI strip):

* Orders today, Revenue today, AOV, On-time delivery %, Open anomalies count (from anomaly\_events)



Middle (time-series + overlays):



* Orders\_count\_daily (90 days) with anomaly flags (join to anomaly\_events)
* Gross\_revenue\_per\_day with anomaly flags
* Avg\_delivery\_time (or on\_time\_rate)



Bottom (tables \& drilldowns):



* anomaly\_events table (sortable by severity) with title + summary + link to details\_json
* detection\_runs summary (run durations, anomalies per run)
* Per-seller / per-category panels for drill-down (top N sellers for a selected anomaly day)



Interaction:



* Click anomaly flag → show summary, details\_json (top sellers, sample rows), suggestion (from details\_json) like “check ingestion duplicates / marketing campaign.”





7\) Demo storyboard (how you present it)



Make a short scripted demo (3–4 minutes):



1. Start dashboard showing stable baseline (no anomalies). Explain agent cadence.
2. Run the volume spike injector (or run it beforehand). Trigger agent run.
3. Show how anomaly\_events appears (HIGH spike), show summary + top seller contributors, open sample raw orders.
4. Run data-quality injector: show nulls/orphans, agent flags data-quality anomaly. Show how detection differs (counts/ratios) and suggested actions.
5. Show detection\_runs timeline and how multiple checks were executed. End with brief note on next steps (optional alerting, ack workflow).

















--------------------------------



The 6 injector scripts (names + purpose)



baseline\_loader — establish/extend the live dataset (normal cadence)



volume\_spike\_injector — create global or seller-level spikes/drops in order volume



ops\_anomaly\_injector — simulate delivery delays / cancellations / status changes



payment\_revenue\_injector — manipulate payments / AOV / payment\_type distribution



data\_quality\_injector — inject nulls, orphans, negative/zero values, duplicate PKs



complex\_scenario\_injector (optional) — combined campaign + data bug (composite event)



Below I describe each in detail.



1\) baseline\_loader (purpose: normal flow)



Goal: Populate live\_\* tables by replaying historical rows so agent has a baseline; used first.



Inputs (params):



start\_date, end\_date (window to replay)



batch\_size (rows per run)



mode: append or refresh (refresh = clear live for window then insert)



injection\_name (e.g., "baseline\_202511")



What it does:



Reads rows from original tables with order\_purchase\_timestamp in window.



Inserts them into live\_orders, live\_order\_items, live\_order\_payments, live\_order\_reviews if not already present (idempotent).



Writes injection\_metadata with injection\_type = baseline\_load and counts.



Optionally triggers detection run for baseline verification.



Why: Get consistent baseline cadence and warm caches/dashboards.



Demo use: Run first to show normal dashboard state: no anomalies.



2\) volume\_spike\_injector (purpose: show traffic anomalies)



Goal: Create sudden spikes or drops in order counts (global or targeted).



Inputs:



target\_date (date to inject spike)



magnitude (multiplier, e.g., 3.0 == 3× baseline)



scope (global, seller\_id, category, state)



mode (insert\_many, duplicate\_existing, scale\_existing\_down for drops)



seed (randomness control)



injection\_name



What it does:



Compute baseline for target\_date (from original + live) to estimate how many orders to add/remove.



If insert\_many: generate synthetic live\_orders rows with realistic fields:



order\_id unique with injection prefix or synthetic PK,



timestamps set to target\_date,



link to valid customer\_id / seller\_id (create synthetic customers/sellers if needed),



create related live\_order\_items and live\_order\_payments.



If duplicate\_existing: copy a set of existing orders but new PKs (fast way to spike).



If scale\_existing\_down: mark many orders as canceled in live\_orders to simulate drop.



Log each insertion into injected\_changes (op=INSERT) and injection\_metadata.



Safety: ensure generated payments/prices look realistic. Use injection\_id prefix on order\_id so agent can identify injected rows.



Demo use: Trigger agent run → observe orders\_count\_daily spike and anomaly\_event.



3\) ops\_anomaly\_injector (purpose: delivery/cancellation ops issues)



Goal: Simulate large-scale delivery delays or mass cancellations.



Inputs:



start\_date, end\_date (window to affect)



anomaly\_type (late\_delivery, mass\_cancellation)



severity (percent of affected orders)



scope (global, seller\_id, state)



halt\_reason (optional textual tag)



What it does:



Selects candidate orders (from union of original + live) in window and scope.



For late\_delivery: update corresponding live\_orders order\_delivered\_customer\_date to far future or set NULL.



For mass\_cancellation: insert live\_order\_status\_changes or insert new live\_orders flagged order\_status='canceled' depending on design.



Log updates in injected\_changes (op=UPDATE) with old\_value\_json and new\_value\_json.



Why: Realistic supply-chain failure scenario.



Demo use: On dashboard, show spike in avg\_delivery\_time, drop in on\_time\_delivery\_rate, and anomaly\_event with top affected sellers.



4\) payment\_revenue\_injector (purpose: revenue \& payment anomalies)



Goal: Create AOV shifts, revenue drops, or payment distribution changes (fraud-like or promo-like).



Inputs:



target\_date, scope



scenario (low\_value\_orders, high\_value\_outliers, payment\_type\_shift, refunds\_inserts)



magnitude (percent change or absolute)



injection\_name



What it does:



low\_value\_orders: create many small-value orders/payments for target\_date.



high\_value\_outliers: insert a few extremely high payment\_value orders to simulate fraud.



payment\_type\_shift: change payment\_type field in many live\_order\_payments for the date to a rare method (e.g., boleto).



refunds\_inserts: insert refund payment records represented in scheme you use.



Log to injected\_changes and injection\_metadata.



Demo use: Observe AOV change, payment\_type distribution panel updates, and anomaly created. Show suggested action: check payment gateway or finance team.



5\) data\_quality\_injector (purpose: integrity \& DQ issues)



Goal: Inject nulls, orphans, negative values, duplicate PKs to exercise DQ checks.



Inputs:



dq\_type (nulls, orphans, negatives, duplicates)



target\_table (orders, order\_items, payments)



percent\_affected (e.g., 10%)



fields\_to\_null (list)



injection\_name



What it does:



nulls: set chosen fields to NULL for selected records (create new live\_\* records or update live\_\*).



orphans: insert order\_items referencing non-existent order\_id, or orders referencing non-existent customer\_id.



negatives: set payment\_value or price to -1 or 0 for some rows.



duplicates: insert duplicate order\_id but with different attributes (ensure PK uniqueness by using injected\_changes scheme or special injected\_order\_id that looks like dup for detection).



Log all changes, include suppression or rollback notes if needed.



Demo use: Agent detects spike in null\_ratio or orphans; anomaly\_events show DQ type and sample bad rows.



6\) complex\_scenario\_injector (optional) — combined events



Goal: A single script that composes 2–3 injectors to create a believable business incident (campaign + backend bug).



Example scenario: Marketing campaign causes volume spike + many duplicate orders due to retry bug → demonstrates composite anomaly where both volume\_spike and data\_quality anomalies happen and agent groups them.



Inputs: config document defining sub-scenarios and order of application.



Why: Powerful demo where agent needs to group related anomalies and show suggested actions.



Orchestration \& Execution flow



Human runs baseline\_loader first (or scheduled) to warm baseline.



For a demo: run volume\_spike\_injector → job\_runs created → detection agent run (manual or auto).



After agent run finishes and anomaly\_events are written, open Grafana/Superset and show anomalies.



For more complex demos, run data\_quality\_injector next and repeat.



Consider a small orchestration script (not full automation) that:



Inserts injection\_metadata (PENDING)



Calls the chosen injector script with injection\_id



On success, marks injection\_metadata DONE and inserts job\_runs for agent



Optionally calls detection runner



(Keep orchestration simple — run-by-run, reproducible, and logged.)



Logging, tagging \& detection integration



All inserted live\_\* rows should carry an injection\_tag column (e.g., inj\_20251111\_volspike) or order\_id with prefix so you can easily query injected rows.



injection\_metadata fields to include: injection\_id, injection\_name, injection\_type, params\_json, started\_at, finished\_at, rows\_inserted, status, notes.



injected\_changes if used should map each change to injection\_id.



Agent should look at injection\_metadata when evaluating anomalies; when anomaly aligns with injection window, include injection\_id in anomaly\_events.details\_json (makes demo narrative crystal clear).



Safety, rollback \& idempotency



Use unique injection\_id and check for existing injection\_metadata to avoid double-applying.



If using injected\_changes, implement rollback logic: read injected\_changes and reverse ops.



For inserts, include a deterministic injected\_pk so re-run will not create duplicates (e.g., composed from injection\_id + counter).



Keep a small rolled\_back lifecycle for test rehearsals.



Testing \& validation checklist (before demo)



&nbsp;baseline\_loader reproduces historical counts in vw\_\* views.



&nbsp;volume\_spike\_injector with magnitude=2x produces visible change in orders\_count\_daily.



&nbsp;ops\_anomaly\_injector causes delivery time / cancellation metrics to shift as expected.



&nbsp;payment\_revenue\_injector changes AOV and payment type distribution panels.



&nbsp;data\_quality\_injector increases null\_ratio/orphan counts.



&nbsp;agent detects anomalies and writes anomaly\_events with details\_json including injection\_id.



&nbsp;rollback works for each injector.



&nbsp;Grafana/Superset panels read from vw\_\* and show injected data and anomaly flags.



Demo run sequence (tight 6–8 minute script)



Show baseline dashboard (no anomalies).



Run volume\_spike\_injector (magnitude 3x global) → trigger agent → show HIGH spike event + top sellers.



Run data\_quality\_injector (nulls in order\_delivered\_customer\_date) → trigger agent → show DQ event, sample bad rows.



Run payment\_revenue\_injector (payment\_type\_shift in region) → trigger agent → show AOV change + payment distribution anomaly.



End: show detection\_runs timeline and injection\_metadata linking each anomaly to an injection.

