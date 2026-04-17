
    
    

select
    HK_CONDUCTING_EQUIPMENT as unique_field,
    count(*) as n_records

from `edh_unreg_silver_dev_st`.`raw_raw_vault`.`hub_conducting_equipment`
where HK_CONDUCTING_EQUIPMENT is not null
group by HK_CONDUCTING_EQUIPMENT
having count(*) > 1


