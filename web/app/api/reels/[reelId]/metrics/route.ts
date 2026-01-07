import { NextRequest, NextResponse } from 'next/server'
import pool from '@/lib/db'

export async function GET(
  request: NextRequest,
  { params }: { params: { reelId: string } }
) {
  try {
    const reelId = params.reelId

    // reel_id로 릴스 찾기
    const reelQuery = `
      SELECT id, reel_id, link, thumbnail_url, author, creator_profile_image, title, music
      FROM reels
      WHERE reel_id = $1
    `
    const reelResult = await pool.query(reelQuery, [reelId])

    if (reelResult.rows.length === 0) {
      return NextResponse.json(
        {
          success: false,
          error: 'Reel not found',
        },
        { status: 404 }
      )
    }

    const reel = reelResult.rows[0]

    // 메트릭 히스토리 조회
    const metricsQuery = `
      SELECT 
        id,
        likes,
        comments,
        views,
        recorded_at
      FROM reel_metrics
      WHERE reel_id = $1
      ORDER BY recorded_at DESC
      LIMIT 100
    `
    const metricsResult = await pool.query(metricsQuery, [reel.id])

    return NextResponse.json({
      success: true,
      data: {
        reel: {
          reel_id: reel.reel_id,
          link: reel.link,
          thumbnail_url: reel.thumbnail_url,
          author: reel.author,
          creator_profile_image: reel.creator_profile_image,
          title: reel.title,
          music: reel.music,
        },
        metrics: metricsResult.rows,
      },
    })
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      {
        success: false,
        error: 'Failed to fetch metrics',
      },
      { status: 500 }
    )
  }
}

