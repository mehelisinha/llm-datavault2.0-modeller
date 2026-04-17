
    
    

select
    HK_CONDUCTING_EQUIPMENT as unique_field,
    count(*) as n_records

from `edh_unreg_silver_dev_st`.`raw_raw_vault`.`sat_conducting_equipment_operational`
where HK_CONDUCTING_EQUIPMENT is not null
group by HK_CONDUCTING_EQUIPMENT
having count(*) > 1


