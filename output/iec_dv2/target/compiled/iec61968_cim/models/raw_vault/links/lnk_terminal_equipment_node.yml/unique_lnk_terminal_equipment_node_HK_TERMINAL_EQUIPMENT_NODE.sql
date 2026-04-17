
    
    

select
    HK_TERMINAL_EQUIPMENT_NODE as unique_field,
    count(*) as n_records

from `edh_unreg_silver_dev_st`.`raw_raw_vault`.`lnk_terminal_equipment_node`
where HK_TERMINAL_EQUIPMENT_NODE is not null
group by HK_TERMINAL_EQUIPMENT_NODE
having count(*) > 1


