import { NextRequest, NextResponse } from 'next/server'
import pool from '@/lib/db'

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const sortBy = searchParams.get('sortBy') || 'views' // 'views', 'likes'
    const limit = parseInt(searchParams.get('limit') || '1000')
    const offset = parseInt(searchParams.get('offset') || '0')
    const startDate = searchParams.get('startDate') // YYYY-MM-DD
    const endDate = searchParams.get('endDate') // YYYY-MM-DD
    const country = searchParams.get('country') || null // kr, jp 등 (없으면 전체)

    const orderBy = sortBy === 'likes' ? 'latest_metric.likes DESC NULLS LAST' : 'latest_metric.views DESC NULLS LAST'

    const queryParams: any[] = [limit, offset]
    let paramIndex = 3
    let startDateParamIndex: number | null = null
    const conditions: string[] = ['(latest_metric.views IS NOT NULL OR latest_metric.likes IS NOT NULL)']

    if (country) {
      conditions.push(`r.country_code = $${paramIndex}`)
      queryParams.push(country)
      paramIndex++
    }
    if (startDate) {
      conditions.push(`r.created_at >= $${paramIndex}`)
      queryParams.push(startDate)
      startDateParamIndex = paramIndex
      paramIndex++
    }
    if (endDate) {
      conditions.push(`r.created_at <= $${paramIndex}::date + INTERVAL '1 day'`)
      queryParams.push(endDate)
      paramIndex++
    }

    const isSingleDay = startDate && endDate && startDate === endDate && startDateParamIndex != null
    const metricDateFilter = isSingleDay ? `AND reel_metrics.recorded_at::date = $${startDateParamIndex}::date` : ''

    const whereClause = conditions.join(' AND ')

    const query = `
      SELECT 
        r.id,
        r.reel_id,
        r.link,
        r.thumbnail_url,
        r.author,
        r.creator_profile_image,
        r.title,
        r.music,
        r.country_code,
        r.created_at,
        latest_metric.likes,
        latest_metric.comments,
        latest_metric.views,
        latest_metric.recorded_at
      FROM instagram_reels r
      LEFT JOIN LATERAL (
        SELECT likes, comments, views, recorded_at
        FROM instagram_reel_metrics
        WHERE reel_id = r.id
        ${metricDateFilter}
        ORDER BY recorded_at DESC
        LIMIT 1
      ) latest_metric ON true
      WHERE ${whereClause}
      ORDER BY ${orderBy}
      LIMIT $1 OFFSET $2
    `

    const result = await pool.query(query, queryParams)

    return NextResponse.json({
      success: true,
      data: result.rows,
      total: result.rowCount,
    })
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch ranking data',
      },
      { status: 500 }
    )
  }
}

