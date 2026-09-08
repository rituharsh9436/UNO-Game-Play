/**
 * Core type definitions for the Real-Time UNO Web Platform.
 * Matches schemas defined in docs.md Section 6.
 */

export type CardColor = "RED" | "BLUE" | "GREEN" | "YELLOW" | "WILD";

export type CardType = "NUMBER" | "ACTION" | "WILD" | "WILD_DRAW_FOUR";

export type CardValue =
  | "0"
  | "1"
  | "2"
  | "3"
  | "4"
  | "5"
  | "6"
  | "7"
  | "8"
  | "9"
  | "SKIP"
  | "REVERSE"
  | "DRAW_TWO"
  | "WILD"
  | "DRAW_FOUR";

export interface Card {
  id: string;
  color: CardColor;
  value: CardValue;
  type: CardType;
  is_playable?: boolean;
}

export type RoomStatus = "WAITING" | "PLAYING" | "FINISHED" | "CLOSED";

export interface Opponent {
  player_id: string;
  nickname: string;
  card_count: number;
  is_host: boolean;
  connected: boolean;
  uno_called: boolean;
  vulnerable_uno: boolean;
}

export interface SanitizedGameState {
  room_code: string;
  status: RoomStatus;
  direction: 1 | -1;
  current_player_id: string;
  turn_deadline_ms: number;
  top_card: Card | null;
  active_color: CardColor;
  draw_pile_count: number;
  discard_pile_count: number;
  pending_draw_count?: number;
  opponents: Opponent[];
  your_hand: Card[];
}

export interface RoomParticipant {
  id: string;
  nickname: string;
  seat_order: number;
  is_host: boolean;
  is_ready: boolean;
  connected: boolean;
  joined_at: string;
}

export interface RoomDetails {
  id: string;
  room_code: string;
  host_player_id: string;
  status: RoomStatus;
  max_players: number;
  house_rules: {
    stack_draw_two?: boolean;
    turn_time_seconds?: number;
  };
  player_count: number;
  players: RoomParticipant[];
  created_at: string;
}

export interface ClientSession {
  room_code: string;
  player_id: string;
  nickname: string;
  is_host: boolean;
  session_token: string;
}
