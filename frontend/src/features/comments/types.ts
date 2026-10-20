export interface SessionComment {
  id: string;
  author_user_id: string;
  author_name: string | null;
  /** Written by the athlete themself, as opposed to a coach or club admin. */
  by_athlete: boolean;
  body: string;
  created_at: string;
  edited_at: string | null;
  /** What the signed-in user may do with it. */
  can_edit: boolean;
  can_delete: boolean;
}

export const MAX_COMMENT_LENGTH = 4000;
