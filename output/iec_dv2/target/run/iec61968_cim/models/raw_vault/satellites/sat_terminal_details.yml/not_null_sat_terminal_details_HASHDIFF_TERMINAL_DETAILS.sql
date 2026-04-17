
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select HASHDIFF_TERMINAL_DETAILS
from `edh_unreg_silver_dev_st`.`raw_raw_vault`.`sat_terminal_details`
where HASHDIFF_TERMINAL_DETAILS is null



  
  
      
    ) dbt_internal_test