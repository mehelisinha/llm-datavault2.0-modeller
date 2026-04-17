
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select HK_TERMINAL_EQUIPMENT_NODE
from `edh_unreg_silver_dev_st`.`raw_staging`.`stg_terminals`
where HK_TERMINAL_EQUIPMENT_NODE is null



  
  
      
    ) dbt_internal_test