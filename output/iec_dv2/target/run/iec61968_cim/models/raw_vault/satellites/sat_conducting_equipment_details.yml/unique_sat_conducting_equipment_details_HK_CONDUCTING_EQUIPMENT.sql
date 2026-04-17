
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    HK_CONDUCTING_EQUIPMENT as unique_field,
    count(*) as n_records

from `edh_unreg_silver_dev_st`.`raw_raw_vault`.`sat_conducting_equipment_details`
where HK_CONDUCTING_EQUIPMENT is not null
group by HK_CONDUCTING_EQUIPMENT
having count(*) > 1



  
  
      
    ) dbt_internal_test