import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, Typography, Card, CardContent, Grid } from '@mui/material';
import { AbstractSection, SectionProps } from './common';


interface OverviewDataRow {
    ticker: string;
    currency: string;
    last_price: number;
    volume: number;
    value: number;
    fee: number;
    invested: number;
    profit: number;
}

interface OverviewResponse {
    base_currency: string;
    overview: Array<OverviewDataRow>;
}

interface OverviewState {
    base_currency: string|undefined;
    investment: number;
    fees: number;
    value: number;
    profit: number;
    overview: Array<OverviewDataRow>;
}

interface OverviewProps {}

export class Overview extends AbstractSection<OverviewProps, OverviewState> {

    sectionName = () => 'Overview';

    constructor(props: OverviewProps & SectionProps) {
        super(props);
        this.state = {
            base_currency: undefined,
            investment: 0,
            fees: 0,
            value: 0,
            profit: 0,
            overview: [],
        };
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadOverview().then(() =>
            this.props.displayProgressBar(false)
        );
    }

    loadOverview() {
        const params = new URLSearchParams();
        // params.append('ticker', 'CEZ.PR');
        return fetch(`/overview/get?${params.toString()}`)
            .then<OverviewResponse>(res => res.json())
            .then(data => this.setState({
                ...data,
                investment: data.overview.reduce((prev, cur, i) => prev + cur.invested, 0),
                fees: data.overview.reduce((prev, cur, i) => prev + cur.fee, 0),
                value: data.overview.reduce((prev, cur, i) => prev + cur.value, 0),
                profit: data.overview.reduce((prev, cur, i) => prev + cur.profit, 0),
            }));
    }

    formatCurrency(value: number, currency?: string): string|null {
        if (value && (this.state.base_currency || currency))
            return value.toLocaleString(undefined, {style: 'currency', currency: currency ? currency : this.state.base_currency});
        return null;
    }

    formatPercents(value: number): string|null {
        if (value)
            return value.toLocaleString(undefined, {style: 'percent', minimumFractionDigits: 1});
        return null;
    }

    render() {

        return (
            <Box>
                <p>TODO Correction for old value + newer investments</p>
                <Grid container spacing={2}>
                    <Grid item xs={3}>
                        <Card elevation={3}>
                            <CardContent>
                                <Typography variant="h5" component="div">Investment</Typography>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.investment)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={3}>
                        <Card elevation={3}>
                            <CardContent>
                                <Typography variant="h5" component="div">Fees</Typography>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.fees)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={3}>
                        <Card elevation={3}>
                            <CardContent>
                                <Typography variant="h5" component="div">Value</Typography>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.value)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={3}>
                        <Card elevation={3}>
                            <CardContent>
                                <Typography variant="h5" component="div">Profit</Typography>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.profit)} ({this.formatPercents(this.state.profit/this.state.investment)})
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow>
                                <TableCell>Ticker</TableCell>
                                <TableCell align='right'>Last price</TableCell>
                                <TableCell align='center'>Volume</TableCell>
                                <TableCell align='right'>Invested</TableCell>
                                <TableCell align='right'>Fee</TableCell>
                                <TableCell align='right'>Value</TableCell>
                                <TableCell colSpan={2} align='center'>Profit</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {this.state.overview.map(
                                (item, i) => <TableRow key={i} sx={{backgroundColor: item.profit < 0 ? 'rgba(255,0,0,0.25)' : 'rgba(0,255,0,0.25)'}}>
                                    <TableCell>{item.ticker}</TableCell>
                                    <TableCell align='right'>{this.formatCurrency(item.last_price, item.currency)}</TableCell>
                                    <TableCell align='center'>{item.volume ? item.volume : null}</TableCell>
                                    <TableCell align='right'>{this.formatCurrency(item.invested)}</TableCell>
                                    <TableCell align='right'>{this.formatCurrency(item.fee)}</TableCell>
                                    <TableCell align='right'>{this.formatCurrency(item.value)}</TableCell>
                                    <TableCell align='right'>{this.formatCurrency(item.profit)}</TableCell>
                                    <TableCell align='right'>{this.formatPercents(item.profit/item.invested)}</TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Box>
        )
    }
}