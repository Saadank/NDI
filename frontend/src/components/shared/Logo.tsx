import Image from "next/image";

interface LogoProps {
  height?: number;
  className?: string;
}

export function Logo({ height = 28, className }: LogoProps) {
  const width = Math.round((height * 127) / 36);
  return (
    <Image
      src="/brand/datarix-logo.svg"
      alt="Datarix"
      width={width}
      height={height}
      className={className}
      priority
    />
  );
}
