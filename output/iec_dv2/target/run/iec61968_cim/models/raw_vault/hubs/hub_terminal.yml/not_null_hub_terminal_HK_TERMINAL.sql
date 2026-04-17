
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select HK_TERMINAL
from `edh_unreg_silver_dev_st`.`raw_raw_vault`.`hub_terminal`
where HK_TERMINAL is null



  
  
      
    ) dbt_internal_test