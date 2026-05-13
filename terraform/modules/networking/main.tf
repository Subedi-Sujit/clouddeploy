################################################################
# Networking Module
# Creates VPC with public and private subnets across 2 AZs.
#
# Public subnets host the ALB (need internet access).
# Private subnets host ECS tasks and RDS (no direct internet).
# NAT Gateway lets private subnets reach the internet for
# package downloads and AWS API calls.
################################################################

# ----------------------------------------------------------------
# VPC
# ----------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-vpc"
  })
}

# ----------------------------------------------------------------
# Internet Gateway - allows public subnets to reach the internet
# ----------------------------------------------------------------
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.tags, {
    Name = "${var.project_name}-igw"
  })
}

# ----------------------------------------------------------------
# Public Subnets (one per AZ)
# Used by: ALB
# ----------------------------------------------------------------
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-public-${var.availability_zones[count.index]}"
    Tier = "public"
  })
}

# ----------------------------------------------------------------
# Private Subnets (one per AZ)
# Used by: ECS tasks, RDS
# ----------------------------------------------------------------
resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name = "${var.project_name}-private-${var.availability_zones[count.index]}"
    Tier = "private"
  })
}

# ----------------------------------------------------------------
# Elastic IP for NAT Gateway
# ----------------------------------------------------------------
# resource "aws_eip" "nat" {
#  domain = "vpc"

 # tags = merge(var.tags, {
  #  Name = "${var.project_name}-nat-eip"
 # })
#}

# ----------------------------------------------------------------
# NAT Gateway (single NAT for cost optimization in dev)
# Production would use one NAT per AZ for high availability.
# ----------------------------------------------------------------
#resource "aws_nat_gateway" "main" {
 # allocation_id = aws_eip.nat.id
  #subnet_id     = aws_subnet.public[0].id

 # tags = merge(var.tags, {
  #  Name = "${var.project_name}-nat"
 # })

  #depends_on = [aws_internet_gateway.main]
#}

# ----------------------------------------------------------------
# Public Route Table - routes 0.0.0.0/0 to IGW
# ----------------------------------------------------------------
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ----------------------------------------------------------------
# Private Route Table - routes 0.0.0.0/0 to NAT Gateway
# ----------------------------------------------------------------
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

 # route {
   # cidr_block     = "0.0.0.0/0"
  #  nat_gateway_id = aws_nat_gateway.main.id
  #}

  tags = merge(var.tags, {
    Name = "${var.project_name}-private-rt"
  })
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}
