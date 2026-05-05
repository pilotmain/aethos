import axios from 'axios';

import {API_BASE_URL, API_PREFIX} from '../../utils/constants';

export const api = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  timeout: 45_000,
  headers: {'Content-Type': 'application/json'},
});

export function setAuthHeader(token: string | null): void {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}
