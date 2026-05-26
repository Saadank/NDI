import Image from "next/image";

interface LogoProps {
  height?: number;
  className?: string;
}

export function Logo({ height = 28, className }: LogoProps) {
  const width = (height * 762) / 130;
  return (
    <Image
      src="/brand/datarix-logo.png"
      alt="Datarix"
      width={width}
      height={height}
      className={className}
      priority
    />
  );
}
