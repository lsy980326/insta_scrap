import { NextResponse } from 'next/server'
import pool from '@/lib/db'

export async function GET() {
  try {
    const result = await pool.query(
      `SELECT DISTINCT country_code FROM instagram_reels WHERE country_code IS NOT NULL ORDER BY country_code`
    )
    const countries = result.rows.map((r: { country_code: string }) => r.country_code)
    return NextResponse.json({ success: true, data: countries })
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      { success: false, error: 'Failed to fetch countries' },
      { status: 500 }
    )
  }
}
