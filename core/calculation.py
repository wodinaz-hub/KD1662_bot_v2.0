import logging
from database import database_manager as db_manager

logger = logging.getLogger('core.calculation')

def calculate_period_results(kvk_name: str, period_key: str):
    """
    Calculates the results for a specific period by comparing Start and End snapshots.
    Saves the results to the kvk_stats table.
    """
    logger.info(f"Starting calculation for {kvk_name} - {period_key}")
    
    # 1. Fetch Start and End snapshots
    start_data = db_manager.get_snapshot_data(kvk_name, period_key, 'start')
    end_data = db_manager.get_snapshot_data(kvk_name, period_key, 'end')
    
    if not start_data:
        logger.warning(f"No START snapshot found for {kvk_name} - {period_key}")
        return False, "Start snapshot missing."
    
    if not end_data:
        logger.warning(f"No END snapshot found for {kvk_name} - {period_key}")
        return False, "End snapshot missing."
        
    results = []
    
    # 2. Iterate through players present in the END snapshot
    # (Players who joined mid-period will have Start stats = 0 effectively, or we can choose to ignore them.
    # Usually, we assume 0 start if missing, or we can skip. Let's assume 0 start for now to include everyone.)
    
    for player_id, end_row in end_data.items():
        start_row = start_data.get(player_id)
        
        # Basic stats
        end_power = end_row['power']
        end_kp = end_row['kill_points']
        end_deaths = end_row['deaths']
        
        if start_row:
            start_power = start_row['power']
            start_kp = start_row['kill_points']
            start_deaths = start_row['deaths']
            
            # Tiers
            diff_t1 = end_row['t1_kills'] - start_row['t1_kills']
            diff_t2 = end_row['t2_kills'] - start_row['t2_kills']
            diff_t3 = end_row['t3_kills'] - start_row['t3_kills']
            diff_t4 = end_row['t4_kills'] - start_row['t4_kills']
            diff_t5 = end_row['t5_kills'] - start_row['t5_kills']
        else:
            # Player wasn't there at start. Treat start as 0? 
            # Or maybe they migrated in. 
            # For safety, let's treat start as 0 but log it? 
            # Actually, if they weren't in start, their "gain" is just their current total?
            # No, that would be huge. 
            # If missing start, we probably shouldn't calculate "gain" blindly or we get their lifetime stats.
            # SAFE APPROACH: Skip players missing start snapshot to avoid massive false positives.
            # OR: Assume they had 0 progress if we can't verify.
            # Let's SKIP for now and log.
            # logger.debug(f"Player {player_id} missing from start snapshot. Skipping.")
            continue

        # Calculate differences
        diff_power = end_power - start_power # Power can be negative
        diff_kp = end_kp - start_kp
        diff_deaths = end_deaths - start_deaths
        
        # Sanity check: KP shouldn't be negative unless bug or reset.
        if diff_kp < 0:
            diff_kp = 0
        if diff_deaths < 0:
            diff_deaths = 0
            
        # Create result object
        result = {
            'player_id': player_id,
            'player_name': end_row['player_name'], # Use name from end snapshot
            'power': end_power, # We usually track current power for requirements, not diff power
            'kill_points': diff_kp,
            'deaths': diff_deaths,
            't1_kills': max(0, diff_t1),
            't2_kills': max(0, diff_t2),
            't3_kills': max(0, diff_t3),
            't4_kills': max(0, diff_t4),
            't5_kills': max(0, diff_t5),
            'kvk_name': kvk_name,
            'period_key': period_key
        }
        results.append(result)
        
    # 3. Save results
    if db_manager.save_period_results(results):
        logger.info(f"Successfully calculated and saved results for {len(results)} players.")
        return True, f"Calculated stats for {len(results)} players."
    else:
        return False, "Database error during save."
