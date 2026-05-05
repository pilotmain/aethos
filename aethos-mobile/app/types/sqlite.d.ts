declare module 'react-native-sqlite-storage' {
  export interface SQLiteDatabase {
    executeSql: (
      sql: string,
      params?: unknown[],
    ) => Promise<[SQLiteResultSet]>;
  }

  export interface SQLiteResultSet {
    rows: {
      length: number;
      item: (index: number) => Record<string, unknown>;
    };
  }

  export interface OpenDatabaseParams {
    name: string;
    location?: string;
  }

  export function enablePromise(enable: boolean): void;
  export function openDatabase(params: OpenDatabaseParams): Promise<SQLiteDatabase>;

  const SQLite: {
    enablePromise: typeof enablePromise;
    openDatabase: typeof openDatabase;
  };

  export default SQLite;
}
