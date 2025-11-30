export interface TurnData {
  // ✅ CONSOLIDATED: starting_possession_team_id removed - use possession_team_id instead
  // possession_team_id represents the team on offense DURING the turn (set before any flips)
  possession_team_id?: string;
  result_type: string;
  ball_handler?: string;
  shooter?: string;
  shooter_id?: string;
  rebounder_player_id?: string;
  rebounding_team?: string;
  rebound_type?: string;
  animations: any[];
  events?: any[];
  [key: string]: any;
}
