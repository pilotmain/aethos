import {create} from 'zustand';

type Ws = {
  activeOrgId: string | null;
  setActiveOrgId: (id: string | null) => void;
};

export const useWorkspaceStore = create<Ws>(set => ({
  activeOrgId: null,
  setActiveOrgId: id => set({activeOrgId: id}),
}));
