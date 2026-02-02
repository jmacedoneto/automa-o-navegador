export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.1"
  }
  public: {
    Tables: {
      automations: {
        Row: {
          browserless_url: string
          created_at: string
          credentials: Json | null
          description: string | null
          erp_url: string
          id: string
          instructions: string
          is_active: boolean | null
          last_execution_at: string | null
          last_execution_status:
            | Database["public"]["Enums"]["execution_status"]
            | null
          name: string
          sheets_url: string
          steps: Json | null
          updated_at: string
          webhook_secret: string | null
          webhook_url: string | null
        }
        Insert: {
          browserless_url: string
          created_at?: string
          credentials?: Json | null
          description?: string | null
          erp_url: string
          id?: string
          instructions: string
          is_active?: boolean | null
          last_execution_at?: string | null
          last_execution_status?:
            | Database["public"]["Enums"]["execution_status"]
            | null
          name: string
          sheets_url: string
          steps?: Json | null
          updated_at?: string
          webhook_secret?: string | null
          webhook_url?: string | null
        }
        Update: {
          browserless_url?: string
          created_at?: string
          credentials?: Json | null
          description?: string | null
          erp_url?: string
          id?: string
          instructions?: string
          is_active?: boolean | null
          last_execution_at?: string | null
          last_execution_status?:
            | Database["public"]["Enums"]["execution_status"]
            | null
          name?: string
          sheets_url?: string
          steps?: Json | null
          updated_at?: string
          webhook_secret?: string | null
          webhook_url?: string | null
        }
        Relationships: []
      }
      execution_logs: {
        Row: {
          automation_id: string
          created_at: string
          error_message: string | null
          extracted_data: Json | null
          finished_at: string | null
          id: string
          schedule_id: string | null
          screenshots: Json | null
          started_at: string
          status: Database["public"]["Enums"]["execution_status"]
          steps_completed: number | null
          total_steps: number | null
          webhook_response: Json | null
        }
        Insert: {
          automation_id: string
          created_at?: string
          error_message?: string | null
          extracted_data?: Json | null
          finished_at?: string | null
          id?: string
          schedule_id?: string | null
          screenshots?: Json | null
          started_at?: string
          status?: Database["public"]["Enums"]["execution_status"]
          steps_completed?: number | null
          total_steps?: number | null
          webhook_response?: Json | null
        }
        Update: {
          automation_id?: string
          created_at?: string
          error_message?: string | null
          extracted_data?: Json | null
          finished_at?: string | null
          id?: string
          schedule_id?: string | null
          screenshots?: Json | null
          started_at?: string
          status?: Database["public"]["Enums"]["execution_status"]
          steps_completed?: number | null
          total_steps?: number | null
          webhook_response?: Json | null
        }
        Relationships: [
          {
            foreignKeyName: "execution_logs_automation_id_fkey"
            columns: ["automation_id"]
            isOneToOne: false
            referencedRelation: "automations"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "execution_logs_schedule_id_fkey"
            columns: ["schedule_id"]
            isOneToOne: false
            referencedRelation: "schedules"
            referencedColumns: ["id"]
          },
        ]
      }
      media_uploads: {
        Row: {
          analysis: Json | null
          automation_id: string | null
          created_at: string
          file_name: string | null
          file_size: number | null
          file_type: Database["public"]["Enums"]["media_type"]
          file_url: string
          id: string
          transcription: string | null
        }
        Insert: {
          analysis?: Json | null
          automation_id?: string | null
          created_at?: string
          file_name?: string | null
          file_size?: number | null
          file_type: Database["public"]["Enums"]["media_type"]
          file_url: string
          id?: string
          transcription?: string | null
        }
        Update: {
          analysis?: Json | null
          automation_id?: string | null
          created_at?: string
          file_name?: string | null
          file_size?: number | null
          file_type?: Database["public"]["Enums"]["media_type"]
          file_url?: string
          id?: string
          transcription?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "media_uploads_automation_id_fkey"
            columns: ["automation_id"]
            isOneToOne: false
            referencedRelation: "automations"
            referencedColumns: ["id"]
          },
        ]
      }
      schedules: {
        Row: {
          automation_id: string
          created_at: string
          cron_expression: string | null
          days_of_week: number[] | null
          id: string
          interval_minutes: number | null
          is_active: boolean | null
          last_run_at: string | null
          next_run_at: string | null
          schedule_type: Database["public"]["Enums"]["schedule_type"]
          time_of_day: string | null
          timezone: string | null
          updated_at: string
        }
        Insert: {
          automation_id: string
          created_at?: string
          cron_expression?: string | null
          days_of_week?: number[] | null
          id?: string
          interval_minutes?: number | null
          is_active?: boolean | null
          last_run_at?: string | null
          next_run_at?: string | null
          schedule_type?: Database["public"]["Enums"]["schedule_type"]
          time_of_day?: string | null
          timezone?: string | null
          updated_at?: string
        }
        Update: {
          automation_id?: string
          created_at?: string
          cron_expression?: string | null
          days_of_week?: number[] | null
          id?: string
          interval_minutes?: number | null
          is_active?: boolean | null
          last_run_at?: string | null
          next_run_at?: string | null
          schedule_type?: Database["public"]["Enums"]["schedule_type"]
          time_of_day?: string | null
          timezone?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "schedules_automation_id_fkey"
            columns: ["automation_id"]
            isOneToOne: false
            referencedRelation: "automations"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      execution_status:
        | "pending"
        | "running"
        | "success"
        | "failed"
        | "cancelled"
      media_type: "image" | "audio" | "video"
      schedule_type: "once" | "daily" | "weekly" | "monthly" | "interval"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      execution_status: [
        "pending",
        "running",
        "success",
        "failed",
        "cancelled",
      ],
      media_type: ["image", "audio", "video"],
      schedule_type: ["once", "daily", "weekly", "monthly", "interval"],
    },
  },
} as const
