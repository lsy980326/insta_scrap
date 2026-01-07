import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const imageUrl = searchParams.get('url')

    if (!imageUrl) {
      return NextResponse.json(
        { error: 'URL parameter is required' },
        { status: 400 }
      )
    }

    console.log('Image proxy request:', imageUrl.substring(0, 100))

    // URL 디코딩 (이미 인코딩된 경우)
    let decodedUrl = imageUrl
    try {
      decodedUrl = decodeURIComponent(imageUrl)
    } catch (e) {
      // 이미 디코딩되었거나 문제가 있는 경우 원본 사용
      decodedUrl = imageUrl
    }

    // Instagram CDN 이미지 가져오기
    const response = await fetch(decodedUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.instagram.com/',
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ko;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'image',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'cross-site',
      },
      redirect: 'follow',
      // 타임아웃 설정
      signal: AbortSignal.timeout(10000), // 10초 타임아웃
    })

    console.log('Image proxy response status:', response.status, response.statusText)

    if (!response.ok) {
      console.error('Image proxy failed:', response.status, response.statusText)
      console.error('Failed URL:', decodedUrl.substring(0, 200))
      
      // 403이나 다른 오류의 경우, 원본 URL을 그대로 반환 (브라우저가 직접 시도)
      // 또는 플레이스홀더 이미지 반환
      if (response.status === 403 || response.status === 404) {
        // Instagram 이미지 URL을 직접 반환 (브라우저가 처리)
        return NextResponse.redirect(decodedUrl, { status: 302 })
      }
      
      return NextResponse.json(
        { 
          error: 'Failed to fetch image',
          status: response.status,
          url: decodedUrl.substring(0, 100)
        },
        { status: response.status }
      )
    }

    const imageBuffer = await response.arrayBuffer()
    const contentType = response.headers.get('content-type') || 'image/jpeg'

    console.log('Image proxy success:', contentType, imageBuffer.byteLength, 'bytes')

    return new NextResponse(imageBuffer, {
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=86400', // 24시간 캐시
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET',
      },
    })
  } catch (error: any) {
    console.error('Image proxy error:', error?.message || error)
    return NextResponse.json(
      { 
        error: 'Internal server error',
        message: error?.message || 'Unknown error'
      },
      { status: 500 }
    )
  }
}

