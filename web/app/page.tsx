'use client'

import { useEffect, useState } from 'react'
import ReelCard from '@/components/ReelCard'
import MetricModal from '@/components/MetricModal'

interface Reel {
  id: number
  reel_id: string
  link: string
  thumbnail_url: string | null
  author: string | null
  creator_profile_image: string | null
  title: string | null
  music: string | null
  likes: number | null
  comments: number | null
  views: number | null
  recorded_at: string | null
  created_at: string
}

interface WeekGroup {
  weekStart: Date
  weekEnd: Date
  reels: Reel[]
}

export default function Home() {
  const [reels, setReels] = useState<Reel[]>([])
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState<'views' | 'likes'>('views')
  const [selectedReel, setSelectedReel] = useState<Reel | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  useEffect(() => {
    fetchReels()
  }, [sortBy, startDate, endDate])

  const fetchReels = async () => {
    setLoading(true)
    try {
      let url = `/api/reels/ranking?sortBy=${sortBy}&limit=1000`
      if (startDate) {
        url += `&startDate=${startDate}`
      }
      if (endDate) {
        url += `&endDate=${endDate}`
      }
      const response = await fetch(url)
      const result = await response.json()
      if (result.success) {
        setReels(result.data)
      }
    } catch (error) {
      console.error('Failed to fetch reels:', error)
    } finally {
      setLoading(false)
    }
  }

  // 일주일 단위로 그룹화
  const groupByWeek = (reels: Reel[]): WeekGroup[] => {
    if (reels.length === 0) return []

    const weekMap = new Map<string, Reel[]>()

    reels.forEach((reel) => {
      const date = new Date(reel.created_at)
      // 주의 시작일 계산 (월요일 기준)
      const dayOfWeek = date.getDay() // 0 = 일요일, 1 = 월요일, ..., 6 = 토요일
      const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek // 월요일로 조정
      const weekStart = new Date(date)
      weekStart.setDate(date.getDate() + diff)
      weekStart.setHours(0, 0, 0, 0)
      
      const weekKey = weekStart.toISOString().split('T')[0]
      
      if (!weekMap.has(weekKey)) {
        weekMap.set(weekKey, [])
      }
      weekMap.get(weekKey)!.push(reel)
    })

    // 주별로 정렬 (최신순)
    const sortedWeeks = Array.from(weekMap.entries()).sort((a, b) => 
      new Date(b[0]).getTime() - new Date(a[0]).getTime()
    )

    return sortedWeeks.map(([weekKey, weekReels]) => {
      const weekStart = new Date(weekKey)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekEnd.getDate() + 6)
      weekEnd.setHours(23, 59, 59, 999)
      
      return {
        weekStart,
        weekEnd,
        reels: weekReels.sort((a, b) => {
          if (sortBy === 'likes') {
            return (b.likes || 0) - (a.likes || 0)
          }
          return (b.views || 0) - (a.views || 0)
        }),
      }
    })
  }

  const handleReelClick = (reel: Reel) => {
    setSelectedReel(reel)
    setShowModal(true)
  }

  const formatNumber = (num: number | null): string => {
    if (num === null) return '0'
    if (num >= 10000) {
      return `${(num / 10000).toFixed(1)}만`
    }
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}천`
    }
    return num.toString()
  }

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString)
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  }

  const formatWeekRange = (weekStart: Date, weekEnd: Date): string => {
    const start = weekStart.toLocaleDateString('ko-KR', {
      month: 'long',
      day: 'numeric',
    })
    const end = weekEnd.toLocaleDateString('ko-KR', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    })
    return `${start} ~ ${end}`
  }

  const weekGroups = groupByWeek(reels)

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-4 text-center">
            Instagram Reels Ranking
          </h1>
          
          {/* 정렬 버튼 */}
          <div className="flex justify-center gap-4 mb-6">
            <button
              onClick={() => setSortBy('views')}
              className={`px-6 py-2 rounded-lg font-semibold transition-all ${
                sortBy === 'views'
                  ? 'bg-primary-500 text-white shadow-lg'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              조회수 순
            </button>
            <button
              onClick={() => setSortBy('likes')}
              className={`px-6 py-2 rounded-lg font-semibold transition-all ${
                sortBy === 'likes'
                  ? 'bg-primary-500 text-white shadow-lg'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              좋아요 순
            </button>
          </div>

          {/* 날짜 범위 필터 */}
          <div className="flex justify-center gap-4 mb-6 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-white text-sm">시작일:</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="px-4 py-2 rounded-lg bg-gray-700 text-white border border-gray-600 focus:outline-none focus:border-primary-500"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-white text-sm">종료일:</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="px-4 py-2 rounded-lg bg-gray-700 text-white border border-gray-600 focus:outline-none focus:border-primary-500"
              />
            </div>
            {(startDate || endDate) && (
              <button
                onClick={() => {
                  setStartDate('')
                  setEndDate('')
                }}
                className="px-4 py-2 rounded-lg bg-gray-600 text-white hover:bg-gray-500 text-sm"
              >
                필터 초기화
              </button>
            )}
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="text-white text-xl">로딩 중...</div>
          </div>
        ) : weekGroups.length === 0 ? (
          <div className="text-center text-gray-400 mt-12">
            데이터가 없습니다.
          </div>
        ) : (
          <div className="space-y-12">
            {weekGroups.map((week, weekIndex) => (
              <div key={weekIndex} className="space-y-4">
                <div className="border-b border-gray-700 pb-2">
                  <h2 className="text-2xl font-bold text-white">
                    {formatWeekRange(week.weekStart, week.weekEnd)}
                  </h2>
                  <p className="text-gray-400 text-sm mt-1">
                    총 {week.reels.length}개 릴스
                  </p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                  {week.reels.map((reel, index) => (
                    <ReelCard
                      key={reel.id}
                      reel={reel}
                      rank={index + 1}
                      onClick={() => handleReelClick(reel)}
                      formatNumber={formatNumber}
                      formatDate={formatDate}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showModal && selectedReel && (
        <MetricModal
          reel={selectedReel}
          onClose={() => {
            setShowModal(false)
            setSelectedReel(null)
          }}
        />
      )}
    </main>
  )
}

