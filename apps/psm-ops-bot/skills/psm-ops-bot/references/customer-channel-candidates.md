# Customer Channel Candidates

This is the review queue for Slack customer-channel auto-tagging in PSM Ops Bot.

Source: Slack `conversations.list` using the `da_ta_hermz` bot token on 2026-05-14. Visibility was public channels only. Private channels were not enumerated because the available token lacked `groups:read`.

C360 tally source: BigQuery-backed Customer 360 data on 2026-05-14.

- Live customer list: 538 customer rows from the same active-customer shape used by `getLiveCustomersFromBigQuery`.
- Broader C360 company/org index: 1,107 company groups from `fct_company_main_deals`, `fct_billing_linked_orgs`, and `dim_org_company`.
- Public customer-channel candidates checked: 37 after `proj-rev-feisiong` was renamed to `proj-cs-feisiong`.
- Live-list tally: 17 clean matches, 8 review matches, 11 not found in live list.
- Broader-index tally: 21 clean matches, 8 review matches, 7 not found.
- `proj-rev-*` public-channel analysis: 18 remaining visible revenue channels after `proj-rev-feisiong` was promoted to `proj-cs-feisiong`; all 18 were closed as not mapped on 2026-05-14.

Do not treat these rows as active mappings. A row can only be copied into the runtime JSON map at `PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH` after `customer_key`, `customer_name`, and `staffany_orgs` are reviewed.

Runtime map row shape:

```json
{
  "channel_id": "C0790P1DQ04",
  "channel_name": "proj-cs-rockproductions",
  "customer_key": "8051493928",
  "customer_name": "Rock Productions Pte Ltd",
  "staffany_orgs": ["Rock Productions"],
  "status": "reviewed"
}
```

## Suggested Customer Mappings

`high_live` means the Slack channel matched the live C360 customer list. `index_only` means C360 has a broader company/org match, but it did not match the live customer list used on the Customer 360 landing page. `review` means the channel matched multiple plausible C360 customers or geography variants. `unmatched` means no reliable C360 company/org text match was found.

Search refinement note: channel slugs can contain noisy prefixes or campaign words that are not in C360, for example `eat-irvins` maps to `Irvins Salted Egg` / `IRVINS Retail`. Future matching passes should strip low-signal prefixes and retry the distinctive brand token before calling a row unmatched.

| Channel | Channel ID | C360 result | Suggested customer key | Suggested customer name | Suggested StaffAny orgs | Notes | Mapping status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `proj-cs-1-group` | `C077E3QNKQU` | `review` | `291698335475` | `1-Group Pte Ltd` | `1-Group`; `1-Group (Melaka)`; `1-SOLEIL` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-bali66` | `C08TTCBBH6W` | `high_live` | `28653991224` | `Double Six` | `Chez Gado Gado Restaurant`; `Dewi Sri Hotel`; `Engine Room`; `Oldman's`; `PT Bali66`; `Sardinia Cafe` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-bata` | `C0AP0JUFK0S` | `review` | `256875778809` | `Bata Shoe (Singapore) Pte Ltd` | `Bata Singapore` | Approved by Kai Yi on 2026-05-14. Nearby C360 text also matched `Batari Group`, treated as false-positive. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-cedele` | `CV14H6MRT` | `high_live` | `30223904667` | `The Bakery Depot Pte Ltd (Cedele)` | `Cedele`; `Cedele HQ` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-dimbulah` | `C01T0R4QGEN` | `manual` | `9003704457` | `Stripes Australia` | `Fonz International Pte Ltd`; `Stripes Australia` | Approved by Kai Yi on 2026-05-14 as `Stripes`. Manual mapping; channel slug does not match C360 name. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-dreamus` | `C0AHT6BMMTP` | `high_live` | `8864467261` | `DreamUs Edutainment Pte Ltd` | `DreamUs Edutainment` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-eat-irvins` | `C097GCHHATZ` | `manual` | `223248107195` | `Irvins Salted Egg` | `IRVINS Retail`; `[Inactive] IRVINS Factory & DC` | Approved by Kai Yi on 2026-05-14. Corrected after manual C360 search for `irvins`; previous matcher failed because channel slug includes `eat-`. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-eightxlifestyle` | `C01RDUG5ABB` | `review` | `5356616581` | `BYD by 1826` | `BYD by 1826` | Approved by Kai Yi on 2026-05-14. Refined search matched deal text `EightX Lifestyle Group`; C360 company name is currently `BYD by 1826`. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-emados` | `C07LW2HTC6A` | `high_live` | `11990799499` | `Emado's` | `Emados` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-eu-yan-sang` | `C08USEGLJRW` | `high_live` | `5217550822` | `Eu Yan Sang International Pte Ltd` | `Eu Yan Sang (Retail)`; `Eu Yan Sang (Warehouse)` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-feisiong` | `C092KB35ECF` | `manual` | `1991281569` | `Fei Siong Group` | `FEI SIONG GROUP`; `FU HUI GEN TANG`; `GOLD EGG`; `ONE THOUSANDS` | Renamed from `proj-rev-feisiong` and verified via Slack `conversations.info` on 2026-05-14. Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-floro` | `C0AUGT47LG2` | `review` | `19381705071` | `FLORO Group` | `Floro Group` | Approved by Kai Yi on 2026-05-14. Raw StaffAny org exists (`org-01KNESWXRNN8D79NH90F1W3XH5`, active headcount 755), but the live `dim_org_company` bridge has `company_id = null`; keep this caveat until C360 bridge is fixed. | `reviewed` |
| `proj-cs-iltm` | `C07BJTE6MNF` | `manual` | `321904638697` | `I Love Taimei` | `I LOVE TAIMEI`; `I LOVE TAIMEI HQ` | Approved by Kai Yi on 2026-05-14: `iltm` means I Love Taimei. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-initia` | `C07CAHENDKK` | `review` | `217447067346` | `INITIA SG` | `Initia Group SG`; `Initia Management` | Approved by Kai Yi on 2026-05-14 as SG entity. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-jacksplace-jppepperdine` | `C08GVQQEQ6L` | `high_live` | `1884420525` | `JP Pepperdine Group Pte Ltd` | `JP PEPPERDINE GROUP PTE. LTD.` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-jumbo` | `C02JF87G1HA` | `high_live` | `2511535497` | `JUMBO Group` | `JUMBO Group`; `JUMBO HQ`; `SIJIMINFU-JUMBO PTE. LTD.` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-kazo` | `C08454F4GSK` | `high_live` | `5157383173` | `Butter Bakery Pte Ltd` | `KAZO` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-kopi-kenangan` | `C09RTN1KEJJ` | `review` | `8444848009` | `Kopi Kenangan` | `Kenangan Coffee Pte Ltd` | Approved by Kai Yi on 2026-05-14. MY match treated as separate entity. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-lo-n-behold` | `C0AEX0MJ2SY` | `high_live` | `23696886817` | `The Lo & Behold Group` | `Claudine`; `Tanjong Beach Club`; `The Coconut Club` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-mexicola` | `C08SU8Q4FQR` | `high_live` | `17082227128` | `Mexicola` | `Da Maria Bali`; `Luigi's Hot Pizza Canggu`; `Mosto Bali`; `Motel Mexicola Canggu`; `Motel Mexicola HO`; `Motel Mexicola Seminyak` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-minmed` | `C01SAMFSFQW` | `index_only` | `3108305119` | `Minmed Group Pte Ltd` | `[Inactive] Minmed Group - Clinics`; `[Inactive] Minmed Group - Hometeam`; `[Inactive] Minmed Group - Locum`; `[Inactive] Minmed Group - Medical Centre`; `[Inactive] Minmed Group - Mobile`; `[Inactive] Minmed Group - Wellness`; `[Inactive] Minmed Group Pte Ltd`; `[inactive] Minmed Group - Locum` | Approved by Kai Yi on 2026-05-14 despite index-only inactive-org caveat. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-munchi` | `C09139W008K` | `review` | `272489698011` | `Munchi Pancakes` | `Munchi Pancakes`; `[Inactive] ALC Rice Bowl` | Approved by Kai Yi on 2026-05-14. Lombok match treated as separate entity. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-neon` | `C08J2RMCAJF` | `review` | `25638156628` | `Victory Hill Exhibitions Pte Ltd` | `Victory Hill Exhibitions Pte. Ltd.` | Approved by Kai Yi on 2026-05-14. Refined search matched `NEON CAPITAL PTE. LTD.` deal text. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-ntuc` | `CTHJ72MHV` | `review` | `9002972285` | `FairPrice Group` | `FairPrice [FFS]`; `FairPrice [Outsourced]` | Approved by Kai Yi on 2026-05-14. Refined search matched `NTUC Fairprice Co-operative Limited` deal text. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-oue` | `C089R5TTMAA` | `index_only` | `319861533406` | `OUE Restaurants Pte Ltd` | `DELIFRANCE SINGAPORE PTE LTD`; `OUE RESTAURANTS & DINING` | Approved by Kai Yi on 2026-05-14 despite index-only caveat. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-pezzo` | `C0139EL9DAL` | `high_live` | `2287609808` | `Pezzo Group (Kiosks Collective)` | `A Noodle Story`; `Crave Foods Pte Ltd` | Approved by Kai Yi on 2026-05-14 despite non-obvious org set. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-playmade` | `C030XLC3B0V` | `review` | `7242744458` | `Playmade` | `Playmade` | Approved by Kai Yi on 2026-05-14. Malaysia match treated as separate entity. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-rhombus` | `C03RQ68G9NK` | `index_only` | `2339765957` | `Rhombus Group` | `Rhombus Group` | Approved by Kai Yi on 2026-05-14 despite historical/index-only caveat. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-rockproductions` | `C0790P1DQ04` | `high_live` | `8051493928` | `Rock Productions Pte Ltd` | `Rock Productions` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-rtg` | `CPWSJ9N1J` | `manual` | `222609488631` | `Royal T Group Pte Ltd` | `LIHO` | Corrected by Kai Yi on 2026-05-14: `rtg` means LiHO / Royal T Group, not Changi Airport Group. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-saigon` | `C07M4UGDWNQ` | `review` | `17227356435` | `Yeu Saigon Group` | `Yeu Saigon Group` | Approved by Kai Yi on 2026-05-14. Manual pick over `La Saigon` and broader `Saigon` candidates. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-seonggong-seorae` | `C0AJAUNCEL8` | `high_live` | `30096254010` | `Seonggong Holdings Pte Ltd` | `SEONGGONG HOLDING GROUP` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-shakeshack` | `C01J34Z9LUR` | `high_live` | `5179522061` | `SPC (Shake Shack)` | `BIGBITECOMPANY GLOBAL PTE. LTD.`; `Eggslut`; `Shake Shack Malaysia Sdn.Bhd.` | Approved by Kai Yi on 2026-05-14 despite broader SPC org set. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-simplyhealth` | `C0224CFUK1T` | `index_only` | `5871638086` | `Simply Health` | `Simply Health Hub LLP` | Approved by Kai Yi on 2026-05-14 despite historical/index-only caveat. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-surreyhills` | `C07T8AHGFC4` | `high_live` | `11578073960` | `Surrey Hills Grocer` | `Surrey Hills Holdings Pte Ltd` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-xcellink` | `C08TQH616PL` | `high_live` | `4070740862` | `Xcellink` | `Xcellink Pte Ltd` | Approved by Kai Yi on 2026-05-14. Ready to copy into runtime map. | `reviewed` |
| `proj-cs-zouk` | `C073168LL8M` | `review` | `4810441301` | `Zouk Singapore` | `Five Guys Singapore Pte Ltd`; `Ichizuke Pte Ltd`; `Zouk Clarke Quay Pte Ltd`; `Zouk Gourmet Pte Ltd`; `Zouk Korio Pte Ltd` | Approved by Kai Yi on 2026-05-14 as Singapore entity. Ready to copy into runtime map. | `reviewed` |

## Revenue Channel Analysis

`proj-rev-*` channels are not customer-channel auto-tag candidates for now. Kai Yi closed the remaining revenue-channel review on 2026-05-14. Do not copy these rows into the runtime customer-channel map unless a channel is later renamed/promoted to `proj-cs-*` or explicitly re-approved.

| Channel | Channel ID | Classification | Suggested customer key | Suggested customer name | Suggested StaffAny orgs | Notes | Mapping status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `proj-rev-abm` | `C08QRT8NWHE` | `not_customer_channel` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/project channel, not auto-tagged. | `not_mapped` |
| `proj-rev-community-sports` | `C096NTK2T08` | `not_customer_channel` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/project channel, not auto-tagged. | `not_mapped` |
| `proj-rev-cosy-dinner` | `C08VCFV7THQ` | `not_customer_channel` |  |  |  | Closed by Kai Yi on 2026-05-14; event/project channel, not auto-tagged. | `not_mapped` |
| `proj-rev-donki` | `C05R3LXE0CE` | `unmatched` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/prospect channel, not auto-tagged. | `not_mapped` |
| `proj-rev-kfc` | `C0AMUAXSJ02` | `unmatched` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/prospect channel, not auto-tagged. | `not_mapped` |
| `proj-rev-lyd` | `C09NBA63TCN` | `review` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/prospect channel, not auto-tagged. | `not_mapped` |
| `proj-rev-mbs` | `C07T2QBDKB4` | `unmatched` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/prospect channel, not auto-tagged. | `not_mapped` |
| `proj-rev-mcdonalds` | `C07TFTGD51R` | `unmatched` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/prospect channel, not auto-tagged. | `not_mapped` |
| `proj-rev-pdt-eelaunch` | `C05GSAN637B` | `not_customer_channel` |  |  |  | Closed by Kai Yi on 2026-05-14; product launch channel, not auto-tagged. | `not_mapped` |
| `proj-rev-prime-supermarket` | `C098CFZ7QBD` | `review` | `4849924663` | `The Supermarket Company Pte Ltd` | `The Supermarket Company Pte Ltd` | Closed by Kai Yi on 2026-05-14; revenue/prospect channel, not auto-tagged. | `not_mapped` |
| `proj-rev-prospectleads` | `C04996FQZN3` | `not_customer_channel` |  |  |  | Closed by Kai Yi on 2026-05-14; prospect lead sourcing channel, not auto-tagged. | `not_mapped` |
| `proj-rev-ps-mid-autumn` | `C096EV1PGH2` | `not_customer_channel` |  |  |  | Closed by Kai Yi on 2026-05-14; PS/event project channel, not auto-tagged. | `not_mapped` |
| `proj-rev-spa-espirit` | `C098ARQGZS6` | `unmatched` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/prospect channel, not auto-tagged. | `not_mapped` |
| `proj-rev-tender` | `C0748L7K6JV` | `not_customer_channel` |  |  |  | Closed by Kai Yi on 2026-05-14; tender project channel, not auto-tagged. | `not_mapped` |
| `proj-rev-tim-ho-wan` | `C08K453537E` | `unmatched` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/prospect channel, not auto-tagged. | `not_mapped` |
| `proj-rev-timhortons` | `C083QREU6HK` | `unmatched` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/prospect channel, not auto-tagged. | `not_mapped` |
| `proj-rev-tools` | `C08E2UXMY2Y` | `not_customer_channel` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue tools/internal channel, not auto-tagged. | `not_mapped` |
| `proj-rev-watsons-my` | `C01NWMRSL3Z` | `unmatched` |  |  |  | Closed by Kai Yi on 2026-05-14; revenue/prospect channel, not auto-tagged. | `not_mapped` |
