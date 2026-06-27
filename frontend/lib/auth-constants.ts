export const AUTH_COOKIE_NAME = "travel_edit_session";
export const AUTH_ROLE_COOKIE = "travel_edit_role";
export const DIRECTOR_UI_USERNAME = "director";

export type SessionUser = {
  id: string;
  username: string;
  displayName: string;
  role: string;
};
