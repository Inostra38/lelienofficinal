export interface Partner {
  id: number;
  nom: string;
  logo: string | null;
}

export interface Link {
  id: number;
  titre: string;
  description: string;
  url: string;
  image: string | null;
  partner: Partner | null;
}

export interface Category {
  id: number;
  nom: string;
  icon_slug: string;
  links: Link[];
}