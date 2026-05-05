import {api} from './client';

export type LoginResponse = {
  token: string;
  token_type: string;
  expires_in_hours: number;
  user: {id: string; name?: string | null};
  organizations: {id: string; name: string; slug: string}[];
};

export async function loginMobile(userId: string, userName?: string): Promise<LoginResponse> {
  const {data} = await api.post<LoginResponse>('/mobile/auth/login', {
    user_id: userId,
    user_name: userName ?? null,
  });
  return data;
}

export async function fetchMe(): Promise<{user_id: string}> {
  const {data} = await api.get<{user_id: string}>('/mobile/me');
  return data;
}
