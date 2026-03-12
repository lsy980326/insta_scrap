'use client'

import { useState } from 'react'

// 일반 img 태그를 사용하는 프로필 이미지 컴포넌트
// Instagram CDN 이미지는 CORS 문제로 직접 로드할 수 없으므로 프록시를 통해 로드
function ProfileImage({ 
  src, 
  alt, 
  className, 
  onError 
}: { 
  src: string
  alt: string
  className?: string
  onError?: (e: React.SyntheticEvent<HTMLImageElement, Event>) => void
}) {
  // 프록시 URL 생성
  const proxyUrl = src ? `/api/image-proxy?url=${encodeURIComponent(src)}` : null
  
  if (!proxyUrl) {
    return null
  }
  
  return (
    <img
      src={proxyUrl}
      alt={alt}
      className={className}
      onError={(e) => {
        onError?.(e)
      }}
      loading="lazy"
    />
  )
}

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

interface ReelCardProps {
  reel: Reel
  rank: number
  onClick: () => void
  formatNumber: (num: number | null) => string
  formatDate: (dateString: string) => string
}

export default function ReelCard({ reel, rank, onClick, formatNumber, formatDate }: ReelCardProps) {
  const [imageError, setImageError] = useState(false)
  const [profileImageError, setProfileImageError] = useState(false)

  return (
    <div
      className="bg-gray-800 rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-all cursor-pointer transform hover:scale-105"
      onClick={onClick}
    >
      {/* 썸네일 */}
      <div className="relative w-full aspect-[9/16] bg-gray-700">
        {reel.thumbnail_url && !imageError ? (
          <img
            src={`/api/image-proxy?url=${encodeURIComponent(reel.thumbnail_url)}`}
            alt={reel.title || 'Reel thumbnail'}
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-500">
            No Image
          </div>
        )}
        
        {/* 랭킹 배지 */}
        <div className="absolute top-2 left-2 bg-primary-500 text-white px-3 py-1 rounded-full font-bold text-sm">
          {rank}위
        </div>

        {/* 통계 오버레이 */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4">
          <div className="flex items-center justify-between text-white">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
              </svg>
              <span className="font-semibold">{formatNumber(reel.views)}</span>
            </div>
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clipRule="evenodd" />
              </svg>
              <span className="font-semibold">{formatNumber(reel.likes)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 정보 */}
      <div className="p-4">
        {reel.author && (
          <div className="flex items-center gap-2 mb-2">
            {reel.creator_profile_image && !profileImageError ? (
              <div className="w-8 h-8 rounded-full overflow-hidden bg-gray-700 flex-shrink-0">
                <ProfileImage
                  src={reel.creator_profile_image}
                  alt={reel.author || 'Profile'}
                  className="w-full h-full object-cover"
                  onError={() => {
                    setProfileImageError(true)
                  }}
                />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center flex-shrink-0">
                <span className="text-gray-400 text-xs">
                  {reel.author.charAt(0).toUpperCase()}
                </span>
              </div>
            )}
            <span className="text-white font-semibold text-sm">@{reel.author}</span>
          </div>
        )}
        {reel.title && (
          <p className="text-gray-300 text-sm line-clamp-2">{reel.title}</p>
        )}
        {reel.music && (
          <p className="text-gray-400 text-xs mt-1 truncate">🎵 {reel.music}</p>
        )}
        {reel.created_at && (
          <p className="text-gray-500 text-xs mt-2">
            등록일: {formatDate(reel.created_at)}
          </p>
        )}
      </div>
    </div>
  )
}

