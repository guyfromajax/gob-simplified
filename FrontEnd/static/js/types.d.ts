export interface TurnData {
  starting_possession_team_id?: string;
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
