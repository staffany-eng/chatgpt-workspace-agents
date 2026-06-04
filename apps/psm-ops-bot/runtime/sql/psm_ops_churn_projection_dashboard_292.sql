-- Source: Metabase card 2446, backing Dashboard 292 "Churn Projection Dashboard".
-- Inspected 2026-05-25. Runtime wraps this fixed BigQuery SQL and applies the
-- rolling renewal-date window plus non-null churn_class filter.

with
get_churn_pct as (
    WITH 
    `pre_raw` as (
          SELECT * FROM (
            SELECT distinct 
                coalesce(organisationName, organisationName) organisation_name,
                coalesce(organisationName, organisationName) organisationName,
                row_number() over (partition by organisationid, startweek order by deal_end desc) uniqueWeekNo,
                * except(organisation_name, organisationName) 
              FROM `analytics.fct_allusages_weekly`
              order by startweek desc
          )
          WHERE uniqueWeekNo = 1
        ),
    `raw` as (
      select 
        (case when de >= current_date THEN 'Active'
        WHEN de < current_date THEN 'Churned'
        Else NULL END) currentContractStatus,
        pre_raw.* 
      from pre_raw
      left join (select row_number() over (partition by organisationid order by startweek desc) rw, organisationid, deal_end de from  pre_raw) using(organisationid)
      where rw = 1
    ),
    `source` as (
      select 
        deal_end_date deal_end,
        s.* except(deal_end),
        ad.* except(company_id)
        -- distinct ad.company_id, 
        -- ad.company_name, 
        -- organisation_name, 
        -- -- contractStatus, 
        -- -- -- Account_Health, 
        -- -- -- All_Usages_Score, 
        -- deal_start_date, 
        -- deal_end_date, 
        -- startweek,
        -- s.* except(startweek)
        -- date_trunc(date_sub(deal_end_date, interval 1 month), month) deal_end_min_1_month 
      from (select row_number() over (partition by company_id order by deal_end_date desc) deal_desc_order, * from (select company_id, deal_end_date, max(total_months) total_months from `analytics.fct_alldealsmrr` group by 1,2)) ad
      left join `raw` s 
        on ad.company_id = s.company_id 
        and s.startweek >= date_trunc(date_sub(deal_end_date, interval 4 week), week(monday)) and s.startweek <= date_trunc(date_sub(deal_end_date, interval 1 week), week(monday))
    ),
    final as (
        SELECT 
          -- date_trunc(startweek, month) startmonth
          `source`.`organisation_name` AS `organisation_name`
          , organisationid
          , company_id
          , deal_desc_order
          , `source`.`deal_end`
          , total_months
          , currentContractStatus
          , min(date(`source`.startweek)) AS `data_from`
          , max(date(`source`.startweek)) AS `data_to`
          , max(`source`.`company_mrr`) AS `company_mrr`
          , max(`source`.`activehc`) AS `activehc`
          , CASE
              WHEN avg(`source`.`combinedcicosuccess`) < 0.8 THEN "1-Red"
              WHEN avg(`source`.`combinedcicosuccess`) >= 0.8 THEN "2-Orange"
              ELSE NULL
          END AS `Account_Health`
          , avg(`source`.`combinedcicosuccess`) AS `0-avg_US`
          , min(`source`.`combinedcicosuccess`) AS `min_US`
          , max(`source`.`combinedcicosuccess`) AS `max_US`
          , sum(`total_mass_grab_request`) AS `1-total_mass_grab_request`
          , 1 - avg((CAST(`source`.`unscheduledsections` AS float64) / CASE WHEN (`source`.`publishedsections` + `source`.`assigningsections` + `source`.`unscheduledsections`) = 0 THEN NULL ELSE (`source`.`publishedsections` + `source`.`assigningsections` + `source`.`unscheduledsections`) END)) AS `2-Scheduled_sections_pct`
        --   , sum(ifnull(`total_shift_request`,0) + ifnull(`total_day_availabilities`,0)) `2-day_shift_availabilities`
          , max(if(activehc=0, 0, `wageset`/activehc)) `3-wage_set_pct`
          , sum(`total_splh_records`) AS `4-total_splh_records`
          , sum(`scheduleViewSwitched`) AS `5-scheduleViewSwitched`
          , max(if(startweek < `tsLockDate`, 1, 0)) AS `6-tsweek_locked`
          , sum(`source`.`total_unclean_timesheets`) AS `7-total_unclean_timesheets`
          , sum(`source`.`ts_exported`) AS `8-ts_exported`
          , max(`customtscreated`) AS `9-customtscreated`
          , max(`isusingtimeclocksidekick`) AS `10-isusingtimeclocksidekick`
          , max(enablepreventearlyclockin or enablepreventlateclockout or enableautoclockout) AS `11-isusing_ts_prevention`
          , sum(`source`.`approvedwma`) AS `12-approvedwma`
          , sum(`shifttagsassigned`) AS `13-shifttagsassigned`
          , sum(shiftQuestionFilled) AS `14-shiftQuestionFilled`
          , sum(`source`.`dayoffsapproved`) AS `15-dayoffsapproved`
          , sum(ifnull(`source`.`leavereportuiview`,0) + ifnull(`source`.`leave_transaction_exported`,0)) AS `16-leavebalance_checking`
          , max(1-(AnnualNegative + nonAnnualNegative) / (totalAudit)) AS `17-positive_leave_pct`
          , max(if(fulltimers=0,0,fulltimers_with_defaultleavehour / fulltimers)) AS `18-defaultleavehour_pct`
          , sum(`source`.`oiltaken`) AS `19-oiltaken`
          , max(if(activehc=0,0, least(totalParticipants / activehc, 1))) AS `20-payrun_participants_pct`
          , sum(`bank_files_downloaded`) AS `21-bank_files_downloaded`
          , sum(`payroll_mpnthly_exported`+`payroll_ytd_exported`) AS `22-payroll_report_exported`
          , sum(costlaborreport_view) AS `23-costlaborreport_view`
          , max(formulated_count) AS `24-formulated_payitem_usage`
          , max(claim_count) AS `25-claim_usage`
          , sum(CASE WHEN `source`.`eaenabled` = TRUE THEN CASE WHEN `source`.`challengestarted` IS NULL THEN 0 ELSE `source`.`challengestarted` END END) + sum(CASE WHEN `source`.`eaenabled` = TRUE THEN CASE WHEN `source`.`redeemed` IS NULL THEN 0 ELSE `source`.`redeemed` END END) AS `26-EA_challenges_rewards`
          
        --   , sum(`source`.`announcementcreated`) AS `announcementcreated`
        FROM `source`
        GROUP BY `organisation_name`, organisationid, company_id, deal_end, deal_desc_order, currentContractStatus, total_months
    ), 
    allusages_score as (
        SELECT 
            IF(`1-total_mass_grab_request` > 0, 1, 0) +
            IF(`2-Scheduled_sections_pct` >= 0.9, 1, 0) +
            IF(`3-wage_set_pct` >= 0.9, 1, 0) +
            IF(`4-total_splh_records` > 0, 1, 0) +
            IF(`5-scheduleViewSwitched` > 0, 1, 0) +
            IF(`6-tsweek_locked` > 0, 1, 0) +
            IF(`7-total_unclean_timesheets` < 100, 1, 0) +
            IF(`8-ts_exported` > 0, 1, 0) +
            IF(`9-customtscreated` > 0, 1, 0) +
            IF(`10-isusingtimeclocksidekick`, 1, 0) +
            IF(`11-isusing_ts_prevention`, 1, 0) +
            IF(`12-approvedwma` > 0, 1, 0) +
            IF(`13-shifttagsassigned` > 0, 1, 0) +
            IF(`14-shiftQuestionFilled` > 0, 1, 0) +
            IF(`15-dayoffsapproved` > 0, 1, 0) +
            IF(`16-leavebalance_checking` > 0, 1, 0) +
            IF(`17-positive_leave_pct` >= 0.9, 1, 0) +
            IF(`18-defaultleavehour_pct` > 0, 1, 0) +
            IF(`19-oiltaken` > 0, 1, 0) +
            IF(`20-payrun_participants_pct` >= 0.9, 1, 0) +
            IF(`21-bank_files_downloaded` > 0, 1, 0) +
            IF(`22-payroll_report_exported` > 0, 1, 0) +
            IF(`23-costlaborreport_view` > 0, 1, 0) +
            IF(`24-formulated_payitem_usage` > 0, 1, 0) +
            IF(`25-claim_usage` > 0, 1, 0) +
            IF(`26-EA_challenges_rewards` > 0, 1, 0) AS `All_Usages_Score`,
            *
        FROM final
    ), 
    account_health_calculation as (
      select 
          CASE
              WHEN `Account_Health` = '2-Orange' and `All_Usages_Score` >= 19 THEN '4-Green Plus'
              WHEN `Account_Health` = '2-Orange' and `All_Usages_Score` >= 11 THEN '3d-Green(11)'
              WHEN `Account_Health` = '2-Orange' and `All_Usages_Score` >= 10 THEN '3c-Green(10)'
              WHEN `Account_Health` = '2-Orange' and `All_Usages_Score` >= 9 THEN '3b-Green(9)'
              WHEN `Account_Health` = '2-Orange' and `All_Usages_Score` >= 8 THEN '3a-Green(8)'
              ELSE `Account_Health`
          END AS `Account_Health`,
          * except (`Account_Health`),
          -- row_number() over (partition by organisationid order by startmonth desc) monthOrderDesc,
          -- row_number() over (partition by organisationid order by startmonth asc) monthOrderAsc,
          if(date_trunc(current_date(), week(monday)) > deal_end, 'Churned', 'Active') contractStatus,
      from allusages_score
      -- order by startmonth desc
    ), 
    ordered_deal as (
      select 
        -- account_health, 
        -- countif(contractstatus = 'Churned') Churned, 
        -- countif(contractstatus = 'Active') Renew, 
        -- round(countif(contractstatus = 'Churned')/count(*),2)*100 Churned_pct 
        -- organisation_name, organisationid, count(*)
        -- row_number() over (partition by organisationid order by deal_end desc) deal_order,
        CASE 
          WHEN deal_desc_order = 1 and currentContractStatus = 'Churned' THEN 'Didnt Renew'
          WHEN deal_desc_order > 1 and currentContractStatus = 'Churned' THEN 'Renewed'
          WHEN currentContractStatus = 'Active' THEN 'Renewed'
          END isContractRenewed,
        * --distinct deal_end
      -- from source 
      from account_health_calculation
      where organisationid is not null
      order by deal_end desc
    ),
    finalCount AS (
      SELECT 
          organisation_name,
          company_mrr,
          deal_end renewal_date,
          isContractRenewed, 
          Account_Health,
          All_Usages_Score,
          data_from,
          data_to,
          total_months
      FROM ordered_deal
      WHERE organisation_name IS NOT NULL
        AND organisation_name != '-'
    ),
    
    grouped AS (
      SELECT 
        CASE 
          WHEN Account_Health LIKE '%Green%' THEN 'Green'
          WHEN Account_Health LIKE '%Orange%' THEN 'Orange'
          WHEN Account_Health LIKE '%Red%' THEN 'Red'
        END AS account_health,
        DATE_TRUNC(DATE(renewal_date), MONTH) AS renewal_period,
        SUM(CASE WHEN isContractRenewed = 'Renewed' THEN total_months ELSE 0 END) AS Renewed,
        SUM(CASE WHEN isContractRenewed != 'Renewed' THEN total_months ELSE 0 END) AS Didnt_Renewed,
        COUNT(*) AS total,
        SUM(total_months) AS total_months
      FROM finalCount
      WHERE isContractRenewed IS NOT NULL
      GROUP BY account_health, renewal_period
    ),
    numbered AS (
      SELECT 
        *,
        DATE_DIFF(renewal_period, DATE("2000-01-01"), MONTH) AS month_number
      FROM grouped
    ),
    final_output AS (
    SELECT 
      FORMAT_DATE('%Y-%m', renewal_period) AS renewal_period,
      account_health,
      Renewed,
      Didnt_Renewed,
      total,
      ROUND(Didnt_Renewed / total, 2) AS churn_pct,
      ROUND(
        SUM(Didnt_Renewed) OVER (
          PARTITION BY account_health 
          ORDER BY month_number
          RANGE BETWEEN 11 PRECEDING AND CURRENT ROW
        ) / SUM(total_months) OVER (
          PARTITION BY account_health 
          ORDER BY month_number
          RANGE BETWEEN 11 PRECEDING AND CURRENT ROW
        )
      , 4) AS accumulative_churn_pct,
      ROW_NUMBER() OVER (PARTITION BY account_health ORDER BY renewal_period DESC) AS row_num
    FROM numbered
    ),
    get_last_pct as (
        SELECT renewal_period, account_health, Renewed, Didnt_Renewed, total, churn_pct, accumulative_churn_pct
        FROM final_output
        WHERE row_num = 1
        ORDER BY account_health
    )
    select account_health, accumulative_churn_pct from get_last_pct
),
get_psm as (
    with deal_psm as (
      select 
        cast(deal_id as string) as deal_id,
        deal_associated_company_id as company_id, 
        deal_end_date,
        deal_psm,
        case
            when deal_psm = '212582784' then 'Sakinah'
            when deal_psm = '228216392' then 'Savira'
            when deal_psm = '192998828' then 'Stan'
            when deal_psm = '51580701' then 'Josica'
            when deal_psm = '236128789' then 'Izzat'
            when deal_psm = '227777035' then 'Khuz'
            when deal_psm = '503162548' then 'Reuben'
            when deal_psm = '208824471' then 'Damba'
            when deal_psm = '160444080' then 'Priska'
			when deal_psm = '367220792' then 'Jessica'
            else deal_psm
        end as deal_psm_name,
        row_number() over (
          partition by deal_associated_company_id
          order by deal_end_date desc
        ) as rw
      from `analytics.dim_deals`
      where deal_psm is not null
        and deal_psm != ''
    )
    select *
    from deal_psm
    where rw = 1
),


company_merge as (
  select
    cast(company_id as string) as company_id,
    cast(canonical_company_id as string) as canonical_company_id
  from analytics.int_hubspot_company_merges
),

deal_merge as (
  select
    cast(deal_id as string) as deal_id,
    cast(canonical_deal_id as string) as canonical_deal_id
  from analytics.int_hubspot_deal_merges
),

`source` as (
   select * from 
( 
  SELECT distinct 
      coalesce(organisationName, organisationName) organisation_name,
      coalesce(organisationName, organisationName) organisationName,
      row_number() over (partition by organisationid, startweek order by deal_end desc) uniqueWeekNo,
      * except(organisation_name, organisationName),
      row_number() over (partition by organisationid order by startweek desc) weekOrder_desc
    FROM `analytics.fct_allusages_weekly`
  )
  where (organisationid is null or weekOrder_desc <= 4)
    order by startweek desc
),
final as (
    SELECT 
      `source`.`organisation_name` AS `organisation_name`
      , `deal_PSM_Name`
      , company_country
      , company_id
      , company_name
      , min(datetime_trunc(datetime(`source`.`deal_since`), day)) AS `deal_start`
      , max(datetime_trunc(datetime(`source`.`deal_end`), day)) AS `deal_end`
      , max(`source`.`company_mrr`) AS `company_mrr`
      , max(`source`.`activehc`) AS `activehc`
      , CASE
        WHEN avg(`source`.`combinedcicosuccess`) < 0.8 THEN "1-Red"
        WHEN avg(`source`.`combinedcicosuccess`) >= 0.8 THEN "2-Orange"
        ELSE NULL
    END AS `Account_Health`
      , avg(`source`.`combinedcicosuccess`) AS `0-avg_US`
      , min(`source`.`combinedcicosuccess`) AS `min_US`
      , max(`source`.`combinedcicosuccess`) AS `max_US`
      , sum(`total_mass_grab_request`) AS `1-total_mass_grab_request`
      , 1 - avg((CAST(`source`.`unscheduledsections` AS float64) / CASE WHEN (`source`.`publishedsections` + `source`.`assigningsections` + `source`.`unscheduledsections`) = 0 THEN NULL ELSE (`source`.`publishedsections` + `source`.`assigningsections` + `source`.`unscheduledsections`) END)) AS `2-Scheduled_sections_pct`
    --   , sum(ifnull(`total_shift_request`,0) + ifnull(`total_day_availabilities`,0)) `2-day_shift_availabilities`
      , max(if(activehc=0, 0, `wageset`/activehc)) `3-wage_set_pct`
      , sum(`total_splh_records`) AS `4-total_splh_records`
      , sum(`scheduleViewSwitched`) AS `5-scheduleViewSwitched`
      , max(if(startweek < `tsLockDate`, 1, 0)) AS `6-tsweek_locked`
      , sum(`source`.`total_unclean_timesheets`) AS `7-total_unclean_timesheets`
      , sum(`source`.`ts_exported`) AS `8-ts_exported`
      , max(`customtscreated`) AS `9-customtscreated`
      , max(`isusingtimeclocksidekick`) AS `10-isusingtimeclocksidekick`
      , max(enablepreventearlyclockin or enablepreventlateclockout or enableautoclockout) AS `11-isusing_ts_prevention`
      , sum(`source`.`approvedwma`) AS `12-approvedwma`
      , sum(`shifttagsassigned`) AS `13-shifttagsassigned`
      , sum(shiftQuestionFilled) AS `14-shiftQuestionFilled`
      , sum(`source`.`dayoffsapproved`) AS `15-dayoffsapproved`
      , sum(ifnull(`source`.`leavereportuiview`,0) + ifnull(`source`.`leave_transaction_exported`,0)) AS `16-leavebalance_checking`
      , max(1-(AnnualNegative + nonAnnualNegative) / (totalAudit)) AS `17-positive_leave_pct`
      , max(if(fulltimers=0,0,fulltimers_with_defaultleavehour / fulltimers)) AS `18-defaultleavehour_pct`
      , sum(`source`.`oiltaken`) AS `19-oiltaken`
      , max(if(activehc=0,0, least(totalParticipants / activehc, 1))) AS `20-payrun_participants_pct`
      , sum(`bank_files_downloaded`) AS `21-bank_files_downloaded`
      , sum(`payroll_mpnthly_exported`+`payroll_ytd_exported`) AS `22-payroll_report_exported`
      , sum(costlaborreport_view) AS `23-costlaborreport_view`
      , max(formulated_count) AS `24-formulated_payitem_usage`
      , max(claim_count) AS `25-claim_usage`
      , sum(CASE WHEN `source`.`eaenabled` = TRUE THEN CASE WHEN `source`.`challengestarted` IS NULL THEN 0 ELSE `source`.`challengestarted` END END) + sum(CASE WHEN `source`.`eaenabled` = TRUE THEN CASE WHEN `source`.`redeemed` IS NULL THEN 0 ELSE `source`.`redeemed` END END) AS `26-EA_challenges_rewards`
      
    --   , sum(`source`.`announcementcreated`) AS `announcementcreated`
    FROM`source`
    left join get_psm using(company_id)
    GROUP BY 1,2,3,4,5 ORDER BY `deal_end` ASC, `organisation_name` ASC
), 
allusages_score as (
    SELECT 
        IF(`1-total_mass_grab_request` > 0, 1, 0) +
        IF(`2-Scheduled_sections_pct` >= 0.9, 1, 0) +
        IF(`3-wage_set_pct` >= 0.9, 1, 0) +
        IF(`4-total_splh_records` > 0, 1, 0) +
        IF(`5-scheduleViewSwitched` > 0, 1, 0) +
        IF(`6-tsweek_locked` > 0, 1, 0) +
        IF(`7-total_unclean_timesheets` < 100, 1, 0) +
        IF(`8-ts_exported` > 0, 1, 0) +
        IF(`9-customtscreated` > 0, 1, 0) +
        IF(`10-isusingtimeclocksidekick`, 1, 0) +
        IF(`11-isusing_ts_prevention`, 1, 0) +
        IF(`12-approvedwma` > 0, 1, 0) +
        IF(`13-shifttagsassigned` > 0, 1, 0) +
        IF(`14-shiftQuestionFilled` > 0, 1, 0) +
        IF(`15-dayoffsapproved` > 0, 1, 0) +
        IF(`16-leavebalance_checking` > 0, 1, 0) +
        IF(`17-positive_leave_pct` >= 0.95, 1, 0) +
        IF(`18-defaultleavehour_pct` > 0.8, 1, 0) +
        IF(`19-oiltaken` > 0, 1, 0) +
        IF(`20-payrun_participants_pct` >= 0.9, 1, 0) +
        IF(`21-bank_files_downloaded` > 0, 1, 0) +
        IF(`22-payroll_report_exported` > 0, 1, 0) +
        IF(`23-costlaborreport_view` > 0, 1, 0) +
        IF(`24-formulated_payitem_usage` > 0, 1, 0) +
        IF(`25-claim_usage` > 0, 1, 0) +
        IF(`26-EA_challenges_rewards` > 0, 1, 0) AS `All_Usages_Score`,
        *
    FROM final
),
proc as (
    select 
        company_id, 
        company_name, 
        deal_psm_name,
        company_country,
        company_mrr, 
        string_agg(organisation_name) orgNames, 
        count(distinct organisation_name) orgCount, 
        string_agg(Account_Health) AccountHealth, 
        min(CAST(SUBSTR(Account_Health, 0, STRPOS(Account_Health, '-') - 1) AS INT64)) minAccountHealth from allusages_score
    group by 1,2,3,4,5
    order by 5 desc
),
org_pivot as (
    select 
        CASE
            WHEN `Account_Health` = '2-Orange' and `All_Usages_Score` >= 19 THEN '4-Green Plus'
            WHEN `Account_Health` = '2-Orange' and `All_Usages_Score` >= 11 THEN '3-Green'
            ELSE `Account_Health`
        END AS `Account_Health`,
        * except (`Account_Health`) 
    from allusages_score
    where deal_end is not null
    -- order by deal_end asc
),
acc_pivot as (
    select 
    company_name, 
    company_id, 
    deal_psm_name,
    company_country,
    company_mrr,
    deal_start, 
    deal_end, 
    date(date_add(deal_end, interval 1 day)) renewal_date,
    CONCAT(
      SUBSTR(CAST(EXTRACT(YEAR FROM date_add(deal_end, interval 1 day)) as STRING),-2), 
      'Q', 
      EXTRACT(QUARTER FROM date_add(deal_end, interval 1 day))
    ) AS renewingQuarter,
    string_agg(concat(organisation_name, ' (', Account_Health,')'), ' | ') orgNames, 
    min(CAST(SUBSTR(Account_Health, 0, STRPOS(Account_Health, '-') - 1) AS INT64)) minAccountHealth,
    round(avg(CAST(SUBSTR(Account_Health, 0, STRPOS(Account_Health, '-') - 1) AS INT64)), 0) avgAccountHealth,
    max(CAST(SUBSTR(Account_Health, 0, STRPOS(Account_Health, '-') - 1) AS INT64)) bestAccountHealth,
    from org_pivot
    group by 1,2,3,4,5,6,7
),

acc_pivot_canonical as (
  select * except(rn)
  from (
    select
      coalesce(cm.canonical_company_id, cast(ap.company_id as string)) as company_id,
      cast(ap.company_id as string) as raw_company_id,
      ap.* except(company_id),
      row_number() over (
        partition by
          coalesce(cm.canonical_company_id, cast(ap.company_id as string)),
          ap.renewal_date
        order by
          -- prefer row yang punya org summary / health
          case when ap.orgNames is not null and ap.orgNames != '' then 1 else 0 end desc,
          case when ap.avgAccountHealth is not null then 1 else 0 end desc,
          -- prefer raw id yang memang canonical
          case when cast(ap.company_id as string) = coalesce(cm.canonical_company_id, cast(ap.company_id as string)) then 1 else 0 end desc,
          ap.company_mrr desc,
          ap.deal_start desc
      ) as rn
    from acc_pivot ap
    left join company_merge cm
      on cast(ap.company_id as string) = cm.company_id
  )
  where rn = 1
),

last_renewal_assessment as (
  select
    company_id,
    renewal_assessment,
    renewal_assessment_reason,
    assessed_end_date,
    main_deal_id
  from (
    select
      coalesce(cm.canonical_company_id, cast(d.deal_associated_company_id as string)) as company_id,
      d.renewal_assessment,
      d.renewal_assessment_reason,
      date(timestamp_millis(safe_cast(d.deal_end_date as int64))) as assessed_end_date,
      coalesce(dm.canonical_deal_id, cast(d.deal_id as string)) as main_deal_id,
      row_number() over (
        partition by coalesce(cm.canonical_company_id, cast(d.deal_associated_company_id as string))
        order by safe_cast(d.deal_end_date as int64) desc
      ) as rw
    from analytics.stg_hubspot__deals d
    left join company_merge cm
      on cast(d.deal_associated_company_id as string) = cm.company_id
    left join deal_merge dm
      on cast(d.deal_id as string) = dm.deal_id
    where d.renewal_assessment is not null
  )
  where rw = 1
),

last_main_paid_deal as (
  select
    company_id,
    renewal_assessment,
    main_end_date,
    main_deal_id
  from (
    select
      coalesce(cm.canonical_company_id, cast(d.deal_associated_company_id as string)) as company_id,
      d.renewal_assessment,
      date(timestamp_millis(safe_cast(d.deal_end_date as int64))) as main_end_date,
      coalesce(dm.canonical_deal_id, cast(d.deal_id as string)) as main_deal_id,
      row_number() over (
        partition by coalesce(cm.canonical_company_id, cast(d.deal_associated_company_id as string))
        order by safe_cast(d.deal_end_date as int64) desc
      ) as rw
    from analytics.stg_hubspot__deals d
    left join company_merge cm
      on cast(d.deal_associated_company_id as string) = cm.company_id
    left join deal_merge dm
      on cast(d.deal_id as string) = dm.deal_id
    where lower(d.deal_name) like '%(main)%'
      and lower(cast(d.hs_is_closed_won as string)) = 'true'
  )
  where rw = 1
),

incoming_unpaid_deals as (
  select * from (
    select
      coalesce(cm.canonical_company_id, cast(f.company_id as string)) as company_id,
      f.frequency,
      f.deal_pipeline,
      f.deal_stage,
      f.deal_end_date as last_deal_end_mrr,
      row_number() over (
        partition by coalesce(cm.canonical_company_id, cast(f.company_id as string))
        order by f.deal_end_date desc
      ) as rw
    from analytics.fct_alldealsmrr f
    left join company_merge cm
      on cast(f.company_id as string) = cm.company_id
    where f.main_product_line = 'Staffany'
  )
  where rw = 1
),

churn_reason as (
    select
        cast(company_id as string) as company_id,
        company_churn_reason,
        company_churn_reason_bucket
    from `analytics.stg_hubspot__companies`
),
get_churn_class as (

  select *,
      case 
          when auto_assessment = "Churned" then
          (
            case
              when last_deal_end_mrr <= deal_end and renewal_assessment = 'Will Renew' and frequency='monthly' then null -- assessed will renew and monthly cycle
              when last_deal_end_mrr <= deal_end then '1-Actualized' -- if the last deal end date contributed to mrr is in the past
              when renewal_assessment = 'Will Not Renew' then '2-Non-Actualized (Confirmed)' -- if it is still contributed to mrr but PS assessed will not renew
              when last_deal_end_mrr > deal_end and renewal_assessment = 'Will Renew' then null -- else if PS assessed will renew
              when renewal_assessment = '50% Will Renew' then '2-Non-Actualized (50% Confirmed)'
              when auto_assessment = 'Red' then '4-Non-Actualized (Red)'
              when auto_assessment = 'Orange' then '5-Non-Actualized (Orange)'    
              when last_deal_end_mrr > deal_end then '3-Non-Actualized (Overdue)'
              -- 50% Won't Renew
              -- Unsure
            end
          )
          when renewal_assessment = 'Will Not Renew' then '2-Non-Actualized (Confirmed)'
          when renewal_assessment = '50% Will Renew' then '2-Non-Actualized (50% Confirmed)'
          when renewal_assessment = 'Will Renew' then null
          when auto_assessment = 'Red' then '4-Non-Actualized (Red)'
          when auto_assessment = 'Orange' then '5-Non-Actualized (Orange)'
      end churn_class,
  from 
  (
      select * except(minAccountHealth, avgAccountHealth, bestAccountHealth, main_deal_id, renewal_assessment, rw),
          coalesce(lra.renewal_assessment, lmp.renewal_assessment) renewal_assessment,
          lmp.main_deal_id last_main_deal_id,
          concat('https://app.hubspot.com/contacts/4137076/record/0-3/',lmp.main_deal_id) last_main_paid_deal_url,
          case 
              WHEN minAccountHealth=1 THEN "1-Red"
              WHEN minAccountHealth=2 THEN "2-Orange"
              WHEN minAccountHealth=3 THEN "3-Green"
          END minAccountHealth,
          case 
              WHEN avgAccountHealth=1 THEN "1-Red"
              WHEN avgAccountHealth=2 THEN "2-Orange"
              WHEN avgAccountHealth=3 THEN "3-Green"
          END avgAccountHealth,
          case 
              WHEN bestAccountHealth=1 THEN "1-Red"
              WHEN bestAccountHealth=2 THEN "2-Orange"
              WHEN bestAccountHealth=3 THEN "3-Green"
          END bestAccountHealth,
          case
              when deal_end < current_date then "Churned"
              WHEN avgAccountHealth=1 THEN "Red"
              WHEN avgAccountHealth=2 THEN "Orange"
          END auto_assessment
          
      from acc_pivot_canonical
      left join last_renewal_assessment lra using(company_id)
      left join last_main_paid_deal lmp using(company_id)
      left join incoming_unpaid_deals iud using(company_id)
      left join churn_reason using(company_id)
  )
),

-- anchor row churn (historical point-in-time)
asof_base as (
  select
    row_number() over(order by cast(company_id as string), renewal_date, deal_end) as churn_row_id,
    gc.*,
    date_trunc(renewal_date, month) as as_of_month
  from get_churn_class gc
),

-- revenue snapshot as-of row month (fallback ke snapshot terakhir <= as_of_month)
rev_asof_ranked as (
  select
    b.churn_row_id,
    r.snapshot_month,
    r.total_arr,
    r.total_mrr,
    r.mrr_staffany,
    r.mrr_engageany,
    r.mrr_payroll,
    row_number() over (
      partition by b.churn_row_id
      order by r.snapshot_month desc
    ) as rn
  from asof_base b
  left join analytics.fct_company_revenue_snapshot r
    on cast(r.company_id as string) = cast(b.company_id as string)
   and r.snapshot_month <= b.as_of_month
),

rev_asof as (
  select * except(rn)
  from rev_asof_ranked
  where rn = 1
),

-- units monthly per company (headcount/section)
units_company_month as (
  select
    cast(company_id as string) as company_id,
    snapshot_month,
    sum(case when lower(main_product_line) = 'staffany'  then headcount_units else 0 end) as headcount_staffany,
    sum(case when lower(main_product_line) = 'engageany' then headcount_units else 0 end) as headcount_engageany,
    sum(case when lower(main_product_line) = 'payroll'   then headcount_units else 0 end) as headcount_payroll,
    sum(case when lower(main_product_line) = 'staffany'  then section_units else 0 end) as section_staffany,
    sum(case when lower(main_product_line) = 'engageany' then section_units else 0 end) as section_engageany,
    sum(case when lower(main_product_line) = 'payroll'   then section_units else 0 end) as section_payroll,
    greatest(
      coalesce(sum(case when lower(main_product_line) = 'staffany'  then headcount_units else 0 end), 0),
      coalesce(sum(case when lower(main_product_line) = 'engageany' then headcount_units else 0 end), 0),
      coalesce(sum(case when lower(main_product_line) = 'payroll'   then headcount_units else 0 end), 0)
    ) as total_headcount_units,
    greatest(
      coalesce(sum(case when lower(main_product_line) = 'staffany'  then section_units else 0 end), 0),
      coalesce(sum(case when lower(main_product_line) = 'engageany' then section_units else 0 end), 0),
      coalesce(sum(case when lower(main_product_line) = 'payroll'   then section_units else 0 end), 0)
    ) as total_section_units
  from analytics.fct_headcount_section_product_snapshot
  group by 1,2
),

units_asof_ranked as (
  select
    b.churn_row_id,
    u.* except(company_id, snapshot_month),
    u.snapshot_month,
    row_number() over (
      partition by b.churn_row_id
      order by u.snapshot_month desc
    ) as rn
  from asof_base b
  left join units_company_month u
    on u.company_id = cast(b.company_id as string)
   and u.snapshot_month <= b.as_of_month
),

units_asof as (
  select * except(rn)
  from units_asof_ranked
  where rn = 1
),

-- years with us as-of row month (start dari reactivation segment terakhir sebelum/as-of)
activity as (
  select
    cast(company_id as string) as company_id,
    snapshot_month,
    case when total_mrr > 0 then 1 else 0 end as is_active
  from analytics.fct_company_revenue_snapshot
), 

activity_flagged as (
  select
    a.*,
    lag(is_active) over (partition by company_id order by snapshot_month) as prev_active
  from activity a
), 

reactivation_starts as (
  select
    company_id,
    snapshot_month as start_month
  from activity_flagged
  where is_active = 1 and (prev_active = 0 or prev_active is null)
), 

reactivation_start_asof as (
  select
    b.churn_row_id,
    max(rs.start_month) as reactivation_start_month
  from asof_base b
  left join reactivation_starts rs
    on rs.company_id = cast(b.company_id as string)
   and rs.start_month <= b.as_of_month
  group by 1
), 

company_industry as (
  select
    cast(company_id as string) as company_id,
    industry_group
  from analytics.dim_companies
)

select
  b.*,

  -- requested cols (as-of)
  date_diff(last_day(b.as_of_month), rsa.reactivation_start_month, year) as number_of_years_with_us,
  ua.total_headcount_units as number_of_active_headcount,
  ua.total_section_units as number_of_sections,
  case
    when ua.total_headcount_units > 0 and ua.total_section_units > 0 then 'Headcount, Section'
    when ua.total_headcount_units > 0 and coalesce(ua.total_section_units, 0) = 0 then 'Headcount'
    when ua.total_section_units > 0 and coalesce(ua.total_headcount_units, 0) = 0 then 'Section'
    else 'None'
  end as type_of_fees,
  ra.total_arr,
  safe_divide(ra.total_mrr, ua.total_headcount_units) as avg_price_per_head,
  safe_divide(ra.total_mrr, ua.total_section_units) as average_price_per_section,
  safe_divide(ra.mrr_staffany, ua.headcount_staffany) as staffany_price_per_head,
  safe_divide(ra.mrr_engageany, ua.headcount_engageany) as engageany_price_per_head,
  safe_divide(ra.mrr_payroll, ua.headcount_payroll) as payroll_price_per_head,
  case
    when ci.industry_group = 'FOOD_BEVERAGES' then 'F&B'
    else 'non-F&B'
  end as industry_bucket,

  -- existing weighted churn logic tetap
  CASE
    WHEN b.churn_class IN ('1-Actualized', '2-Non-Actualized (Confirmed)') THEN b.company_mrr
    WHEN b.churn_class IN ('2-Non-Actualized (50% Confirmed)') THEN 0.5 * b.company_mrr
    WHEN b.churn_class = '3-Non-Actualized (Overdue)' THEN 0.1 * b.company_mrr
    WHEN b.churn_class like '%Non-Actualized%' THEN (
      CASE
        WHEN b.avgAccountHealth like '%Orange%' THEN (select accumulative_churn_pct from get_churn_pct where Account_Health = 'Orange') * b.company_mrr
        WHEN b.avgAccountHealth like '%Red%' THEN (select accumulative_churn_pct from get_churn_pct where Account_Health = 'Red') * b.company_mrr
      END
    )
  END as weighted_churn_mrr

from asof_base b
left join rev_asof ra on ra.churn_row_id = b.churn_row_id
left join units_asof ua on ua.churn_row_id = b.churn_row_id
left join reactivation_start_asof rsa on rsa.churn_row_id = b.churn_row_id
left join company_industry ci on ci.company_id = cast(b.company_id as string)
