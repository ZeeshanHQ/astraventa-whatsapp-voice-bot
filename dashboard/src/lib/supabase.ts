import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://iepnohbpbfdfdinotaat.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllcG5vaGJwYmZkZmRpbm90YWF0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTM2MTkzNTksImV4cCI6MjEwOTE5NTM1OX0.gFbue5c0UnCp5RmnVSIeFouN7G1-qOFS_YWkmCU8okE';

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
  },
  realtime: {
    params: {
      eventsPerSecond: 10,
    },
  },
});
