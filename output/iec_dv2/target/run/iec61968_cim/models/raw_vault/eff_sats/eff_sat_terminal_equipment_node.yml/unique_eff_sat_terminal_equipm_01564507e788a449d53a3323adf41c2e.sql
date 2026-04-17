
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    HK_TERMINAL_EQUIPMENT_NODE as unique_field,
    count(*) as n_records

from `edh_unreg_silver_dev_st`.`raw_raw_vault`.`eff_sat_terminal_equipment_node`
where HK_TERMINAL_EQUIPMENT_NODE is not null
group by HK_TERMINAL_EQUIPMENT_NODE
having count(*) > 1



  
  
      
    ) dbt_internal_test