export interface Athlete {
  id: string;
  user_id: string | null;
  club_id: string | null;
  display_name: string;
  birthdate: string | null;
  sex: Sex | null;
  height_cm: number | null;
  /** UCI age category code (U11…U23, ELITE, M30, M35…), from the birthdate. */
  category: string | null;
}

export type Sex = "female" | "male";
