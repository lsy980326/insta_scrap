import { NextRequest, NextResponse } from 'next/server'
import pool from '@/lib/db'

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const sortBy = searchParams.get('sortBy') || 'views' // 'views', 'likes'
    const limit = parseInt(searchParams.get('limit') || '1000') // 일주일 단위 그룹화를 위해 충분히 많은 데이터 가져오기
    const offset = parseInt(searchParams.get('offset') || '0')
    const startDate = searchParams.get('startDate') // YYYY-MM-DD 형식
    const endDate = searchParams.get('endDate') // YYYY-MM-DD 형식

    // 정렬 기준에 따른 쿼리
    const orderBy = sortBy === 'likes' ? 'latest_metric.likes DESC NULLS LAST' : 'latest_metric.views DESC NULLS LAST'

    // 날짜 필터 조건 추가
    let dateFilter = ''
    const queryParams: any[] = [limit, offset]
    let paramIndex = 3

    if (startDate) {
      dateFilter += ` AND r.created_at >= $${paramIndex}`
      queryParams.push(startDate)
      paramIndex++
    }
    if (endDate) {
      dateFilter += ` AND r.created_at <= $${paramIndex}::date + INTERVAL '1 day'`
      queryParams.push(endDate)
      paramIndex++
    }

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
        r.created_at,
        latest_metric.likes,
        latest_metric.comments,
        latest_metric.views,
        latest_metric.recorded_at
      FROM reels r
      LEFT JOIN LATERAL (
        SELECT likes, comments, views, recorded_at
        FROM reel_metrics
        WHERE reel_id = r.id
        ORDER BY recorded_at DESC
        LIMIT 1
      ) latest_metric ON true
      WHERE (latest_metric.views IS NOT NULL OR latest_metric.likes IS NOT NULL)
        ${dateFilter}
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

