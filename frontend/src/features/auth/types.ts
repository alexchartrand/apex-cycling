export interface User {
  id: string;
  email: string;
  is_platform_admin: boolean;
}

export interface SignupPayload {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}
