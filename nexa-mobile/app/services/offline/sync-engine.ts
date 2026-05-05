import NetInfo from '@react-native-community/netinfo';
import SQLite, {type SQLiteDatabase} from 'react-native-sqlite-storage';

import {fetchMobileSync, type MobileSyncPayload} from '../api/mobile';

SQLite.enablePromise(true);

const DB_NAME = 'nexa_mobile.db';

export type LocalProjectRow = {
  id: string;
  name: string;
  goal: string;
  status: string;
  organization_id: string | null;
  updated_at: string;
};

export type LocalTaskRow = {
  id: string;
  title: string;
  description: string | null;
  status: string;
  project_id: string | null;
  assigned_to: string | null;
  updated_at: string;
};

export type LocalMemberRow = {
  id: string;
  user_id: string;
  user_name: string | null;
  role: string;
};

/**
 * Offline cache + pull sync for Mission Control data (Phase 34b).
 */
class SyncEngine {
  private db: SQLiteDatabase | null = null;
  private syncInterval: ReturnType<typeof setInterval> | null = null;
  private netUnsubscribe: (() => void) | null = null;

  async init(): Promise<void> {
    if (this.db) {
      return;
    }
    this.db = await SQLite.openDatabase({name: DB_NAME, location: 'default'});
    await this.createTables();
    this.setupNetworkListener();
    this.startPeriodicSync();
    await this.syncDown().catch(() => undefined);
  }

  async createTables(): Promise<void> {
    const db = this.requireDb();
    await db.executeSql(
      `CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT,
        goal TEXT,
        status TEXT,
        organization_id TEXT,
        updated_at TEXT
      );`,
    );
    await db.executeSql(
      `CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT,
        description TEXT,
        status TEXT,
        project_id TEXT,
        assigned_to TEXT,
        updated_at TEXT
      );`,
    );
    await db.executeSql(
      `CREATE TABLE IF NOT EXISTS team_members (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        user_name TEXT,
        role TEXT
      );`,
    );
  }

  async syncDown(): Promise<void> {
    const net = await NetInfo.fetch();
    if (!net.isConnected) {
      return;
    }
    let payload;
    try {
      payload = await fetchMobileSync();
    } catch {
      return;
    }
    await this.saveProjects(payload.projects);
    await this.saveTasks(payload.tasks);
    await this.saveTeam(payload.team);
  }

  async saveProjects(projects: MobileSyncPayload['projects']): Promise<void> {
    const db = this.requireDb();
    for (const p of projects) {
      await db.executeSql(
        `INSERT OR REPLACE INTO projects (id, name, goal, status, organization_id, updated_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
        [p.id, p.name, p.goal, p.status, p.organization_id ?? null, p.updated_at],
      );
    }
  }

  async saveTasks(tasks: MobileSyncPayload['tasks']): Promise<void> {
    const db = this.requireDb();
    for (const t of tasks) {
      await db.executeSql(
        `INSERT OR REPLACE INTO tasks (id, title, description, status, project_id, assigned_to, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [
          t.id,
          t.title,
          t.description ?? null,
          t.status,
          t.project_id ?? null,
          t.assigned_to ?? null,
          t.updated_at,
        ],
      );
    }
  }

  async saveTeam(team: MobileSyncPayload['team']): Promise<void> {
    const db = this.requireDb();
    for (const m of team) {
      await db.executeSql(
        `INSERT OR REPLACE INTO team_members (id, user_id, user_name, role)
         VALUES (?, ?, ?, ?)`,
        [m.id, m.user_id, m.user_name ?? null, m.role],
      );
    }
  }

  async getProjects(): Promise<LocalProjectRow[]> {
    const db = this.requireDb();
    const [res] = await db.executeSql('SELECT * FROM projects ORDER BY updated_at DESC');
    const rows: LocalProjectRow[] = [];
    for (let i = 0; i < res.rows.length; i++) {
      const r = res.rows.item(i);
      rows.push({
        id: String(r.id),
        name: String(r.name),
        goal: String(r.goal),
        status: String(r.status),
        organization_id: r.organization_id != null ? String(r.organization_id) : null,
        updated_at: String(r.updated_at),
      });
    }
    return rows;
  }

  async getTasksForProject(projectId: string): Promise<LocalTaskRow[]> {
    const db = this.requireDb();
    const [res] = await db.executeSql(
      'SELECT * FROM tasks WHERE project_id = ? ORDER BY updated_at DESC',
      [projectId],
    );
    const rows: LocalTaskRow[] = [];
    for (let i = 0; i < res.rows.length; i++) {
      const r = res.rows.item(i);
      rows.push({
        id: String(r.id),
        title: String(r.title),
        description: r.description != null ? String(r.description) : null,
        status: String(r.status),
        project_id: r.project_id != null ? String(r.project_id) : null,
        assigned_to: r.assigned_to != null ? String(r.assigned_to) : null,
        updated_at: String(r.updated_at),
      });
    }
    return rows;
  }

  startPeriodicSync(intervalMs = 300_000): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
    }
    this.syncInterval = setInterval(() => {
      void this.syncDown();
    }, intervalMs);
  }

  setupNetworkListener(): void {
    if (this.netUnsubscribe) {
      this.netUnsubscribe();
    }
    this.netUnsubscribe = NetInfo.addEventListener(state => {
      if (state.isConnected) {
        void this.syncDown();
      }
    });
  }

  private requireDb(): SQLiteDatabase {
    if (!this.db) {
      throw new Error('SyncEngine not initialized');
    }
    return this.db;
  }
}

export const syncEngine = new SyncEngine();
