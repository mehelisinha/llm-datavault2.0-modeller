
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    HK_TERMINAL as unique_field,
    count(*) as n_records

from `edh_unreg_silver_dev_st`.`raw_raw_vault`.`hub_terminal`
where HK_TERMINAL is not null
group by HK_TERMINAL
having count(*) > 1



  
  
      
    ) dbt_internal_test