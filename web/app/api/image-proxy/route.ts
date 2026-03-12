import { NextRequest, NextResponse } from 'next/server'
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3'

const s3 = new S3Client({
  region: process.env.AWS_REGION || 'us-east-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
  },
})

const S3_BUCKET = process.env.S3_BUCKET || 'trendboard-mda'
const S3_HOST = `.s3.`  // S3 URL 감지용

function extractS3Key(url: string): string | null {
  try {
    const parsed = new URL(url)
    // https://{bucket}.s3.{region}.amazonaws.com/{key}
    if (parsed.hostname.includes(S3_HOST) && parsed.hostname.includes('amazonaws.com')) {
      return parsed.pathname.slice(1) // 앞의 / 제거
    }
  } catch {}
  return null
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const imageUrl = searchParams.get('url')

    if (!imageUrl) {
      return NextResponse.json({ error: 'URL parameter is required' }, { status: 400 })
    }

    let decodedUrl = imageUrl
    try {
      decodedUrl = decodeURIComponent(imageUrl)
    } catch {}

    // S3 URL이면 SDK로 가져오기
    const s3Key = extractS3Key(decodedUrl)
    if (s3Key) {
      const command = new GetObjectCommand({ Bucket: S3_BUCKET, Key: s3Key })
      const s3Response = await s3.send(command)
      const body = await s3Response.Body?.transformToByteArray()
      if (!body) {
        return NextResponse.json({ error: 'Empty S3 response' }, { status: 500 })
      }
      return new NextResponse(body, {
        headers: {
          'Content-Type': s3Response.ContentType || 'image/webp',
          'Cache-Control': 'public, max-age=86400',
          'Access-Control-Allow-Origin': '*',
        },
      })
    }

    // Instagram CDN 이미지
    const response = await fetch(decodedUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.instagram.com/',
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
      },
      redirect: 'follow',
      signal: AbortSignal.timeout(10000),
    })

    if (!response.ok) {
      if (response.status === 403 || response.status === 404) {
        return NextResponse.redirect(decodedUrl, { status: 302 })
      }
      return NextResponse.json({ error: 'Failed to fetch image', status: response.status }, { status: response.status })
    }

    const imageBuffer = await response.arrayBuffer()
    const contentType = response.headers.get('content-type') || 'image/jpeg'

    return new NextResponse(imageBuffer, {
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=86400',
        'Access-Control-Allow-Origin': '*',
      },
    })
  } catch (error: any) {
    console.error('Image proxy error:', error?.message || error)
    return NextResponse.json({ error: 'Internal server error', message: error?.message }, { status: 500 })
  }
}
