import AsyncStorage from '@react-native-async-storage/async-storage';
import {create} from 'zustand';
import {createJSONStorage, persist} from 'zustand/middleware';

import {setAuthHeader} from '../services/api/client';
import {saveToken} from '../services/storage';

type OrgLite = {id: string; name: string; slug: string};

type AuthState = {
  token: string | null;
  userId: string | null;
  userName: string | null;
  organizations: OrgLite[];
  setSession: (
    token: string,
    userId: string,
    userName?: string | null,
    organizations?: OrgLite[],
  ) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      userId: null,
      userName: null,
      organizations: [],
      setSession: (token, userId, userName, organizations) => {
        setAuthHeader(token);
        void saveToken(token);
        set({
          token,
          userId,
          userName: userName ?? null,
          organizations: organizations ?? get().organizations,
        });
      },
      logout: () => {
        setAuthHeader(null);
        void saveToken(null);
        set({token: null, userId: null, userName: null, organizations: []});
      },
    }),
    {
      name: 'nexa-mobile-auth',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: s => ({
        token: s.token,
        userId: s.userId,
        userName: s.userName,
        organizations: s.organizations,
      }),
    },
  ),
);
