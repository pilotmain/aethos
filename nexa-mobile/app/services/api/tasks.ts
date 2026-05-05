import {api} from './client';

export async function createTask(payload: {
  title: string;
  project_id?: string | null;
  description?: string | null;
}) {
  const {data} = await api.post('/mobile/tasks', payload);
  return data as {task: {id: string; title: string; status: string}};
}

export async function patchTaskStatus(taskId: string, status: string) {
  const {data} = await api.patch(`/mobile/tasks/${taskId}`, {status});
  return data as {task: {id: string; title: string; status: string}};
}
